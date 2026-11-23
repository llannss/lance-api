"""GPU Nexus Marketplace: used-GPU listings, their photos, and messages
between buyers and sellers.

Every route needs a signed-in account and takes it from the login token,
never from the request body, so nobody can list, edit or message as someone
else. Photos are uploaded first (POST /listings/photos) and the returned
URLs are then attached to a listing; the API only accepts URLs of photos the
same account uploaded.
"""

import secrets
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, Response, UploadFile
from pydantic import BaseModel, Field, field_validator

import images
from database import (
    ConversationRepository,
    GPURepository,
    ListingPhotoStore,
    ListingRepository,
    MessageRepository,
    RateLimiter,
    UserRepository,
    get_conversation_repository,
    get_listing_photo_store,
    get_listing_repository,
    get_message_repository,
    get_rate_limiter,
    get_repository,
    get_user_repository,
)
from models import MAX_ID
from security import enforce_rate_limit, get_current_user

router = APIRouter(tags=["Marketplace"])

MAX_PHOTOS = 6
PHOTO_MAX_SIDE = 1600                # Marketplace photos keep more detail than catalog shots
LISTINGS_PER_PAGE = 60
# (window seconds, max hits) per account
PHOTO_UPLOADS = (60 * 60, 60)
NEW_LISTINGS = (60 * 60, 10)
NEW_MESSAGES = (10 * 60, 40)

LISTING_NOT_FOUND = "Listing not found."
CONVERSATION_NOT_FOUND = "Conversation not found."

ListingId = Path(ge=1, le=MAX_ID, description="The ID of the listing.")
ConversationId = Path(ge=1, le=MAX_ID, description="The ID of the conversation.")
Condition = Literal["new", "like_new", "good", "fair", "for_parts"]


# ---------- request and response shapes ----------

class ListingIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=2000)
    condition: Condition
    price: float = Field(gt=0, lt=100_000_000)
    currency: Literal["PHP", "USD"] = "PHP"
    location: str = Field(default="", max_length=80)
    photos: list[str] = Field(default_factory=list, max_length=MAX_PHOTOS)
    gpu_id: int | None = Field(default=None, ge=1, le=MAX_ID)

    @field_validator("title", "description", "location")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    condition: Condition | None = None
    price: float | None = Field(default=None, gt=0, lt=100_000_000)
    currency: Literal["PHP", "USD"] | None = None
    location: str | None = Field(default=None, max_length=80)
    photos: list[str] | None = Field(default=None, max_length=MAX_PHOTOS)
    gpu_id: int | None = Field(default=None, ge=1, le=MAX_ID)
    status: Literal["active", "sold"] | None = None

    @field_validator("title", "description", "location")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Write a message first.")
        return value


# ---------- helpers ----------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _name(email: str | None) -> str:
    """What other people see: the part of the email before the @."""
    return (email or "").split("@")[0] or "GPU Nexus member"


def _check_photos(urls: list[str], user_id: int) -> list[str]:
    """Only this account's own uploads, each once, in the given order."""
    clean: list[str] = []
    for url in urls:
        path = ListingPhotoStore.path_from_url(url)
        if not path or not path.startswith(f"u{user_id}-"):
            raise HTTPException(status_code=422, detail="Upload your photos through the Marketplace first.")
        if url not in clean:
            clean.append(url)
    return clean


def _check_gpu(gpu_id: int | None, gpus: GPURepository) -> None:
    if gpu_id is not None and gpus.get(gpu_id) is None:
        raise HTTPException(status_code=422, detail="That GPU isn't in the catalog.")


def _gpu_summary(gpu: dict | None) -> dict | None:
    if not gpu:
        return None
    keys = ("id", "brand", "model", "series", "vram", "release_date", "launch_price_usd", "image_url")
    return {k: gpu.get(k) for k in keys}


def _present(rows: list[dict], user: dict, gpus: GPURepository, users: UserRepository) -> list[dict]:
    """Listings as the Marketplace shows them: with the GPU and the seller's name."""
    gpu_ids = [r["gpu_id"] for r in rows if r.get("gpu_id")]
    by_gpu = {g["id"]: g for g in gpus.get_many(gpu_ids)} if gpu_ids else {}
    emails = users.emails([r["seller_id"] for r in rows])
    return [{
        **row,
        "price": float(row["price"]),
        "gpu": _gpu_summary(by_gpu.get(row.get("gpu_id"))),
        "seller": {"id": row["seller_id"], "name": _name(emails.get(int(row["seller_id"])))},
        "is_mine": int(row["seller_id"]) == int(user["id"]),
    } for row in rows]


def _own_listing(listing_id: int, user: dict, listings: ListingRepository, allow_admin: bool = False) -> dict:
    listing = listings.get(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail=LISTING_NOT_FOUND)
    mine = int(listing["seller_id"]) == int(user["id"])
    if not mine and not (allow_admin and user.get("role") == "admin"):
        raise HTTPException(status_code=403, detail="You can only change your own listings.")
    return listing


# ---------- listings ----------

@router.get("/listings")
def list_listings(
    gpu_id: int | None = Query(default=None, ge=1, le=MAX_ID, description="Only listings of this catalog GPU."),
    mine: bool = Query(default=False, description="Only your own listings, active and sold."),
    page: int = Query(default=1, ge=1, le=1000),
    user: dict = Depends(get_current_user),
    listings: ListingRepository = Depends(get_listing_repository),
    gpus: GPURepository = Depends(get_repository),
    users: UserRepository = Depends(get_user_repository),
):
    """Listings, newest first: active ones from everyone, or all of yours."""
    rows, total = listings.list(
        status=None if mine else "active",
        gpu_id=gpu_id,
        seller_id=user["id"] if mine else None,
        limit=LISTINGS_PER_PAGE,
        offset=(page - 1) * LISTINGS_PER_PAGE,
    )
    return {"total": total, "page": page, "per_page": LISTINGS_PER_PAGE,
            "listings": _present(rows, user, gpus, users)}


@router.get("/listings/{listing_id}")
def get_listing(
    listing_id: int = ListingId,
    user: dict = Depends(get_current_user),
    listings: ListingRepository = Depends(get_listing_repository),
    gpus: GPURepository = Depends(get_repository),
    users: UserRepository = Depends(get_user_repository),
):
    listing = listings.get(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail=LISTING_NOT_FOUND)
    return _present([listing], user, gpus, users)[0]


@router.post("/listings", status_code=201)
def create_listing(
    body: ListingIn,
    user: dict = Depends(get_current_user),
    listings: ListingRepository = Depends(get_listing_repository),
    gpus: GPURepository = Depends(get_repository),
    users: UserRepository = Depends(get_user_repository),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Put a GPU up for sale. Photos must already be uploaded by this account."""
    enforce_rate_limit(limiter, f"listing-new:{user['id']}", *NEW_LISTINGS,
                       "You've posted a lot of listings this hour. Try again later.")
    _check_gpu(body.gpu_id, gpus)
    row = {**body.model_dump(), "photos": _check_photos(body.photos, user["id"]), "seller_id": user["id"]}
    return _present([listings.create(row)], user, gpus, users)[0]


@router.patch("/listings/{listing_id}")
def update_listing(
    body: ListingUpdate,
    listing_id: int = ListingId,
    user: dict = Depends(get_current_user),
    listings: ListingRepository = Depends(get_listing_repository),
    gpus: GPURepository = Depends(get_repository),
    users: UserRepository = Depends(get_user_repository),
    store: ListingPhotoStore = Depends(get_listing_photo_store),
):
    """Change your listing, or mark it sold (status "sold") or for sale again."""
    listing = _own_listing(listing_id, user, listings)
    changes = body.model_dump(exclude_unset=True)
    if "gpu_id" in changes:
        _check_gpu(changes["gpu_id"], gpus)
    if "photos" in changes:
        changes["photos"] = _check_photos(changes["photos"] or [], user["id"])
    for required in ("title", "condition", "price", "currency", "status"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=422, detail=f"{required} can't be empty.")
    if not changes:
        return _present([listing], user, gpus, users)[0]
    updated = listings.update(listing_id, changes)
    if updated is None:
        raise HTTPException(status_code=404, detail=LISTING_NOT_FOUND)
    # photos taken off the listing are deleted from storage
    if "photos" in changes:
        for url in set(listing.get("photos") or []) - set(changes["photos"]):
            store.remove_url(url)
    return _present([updated], user, gpus, users)[0]


@router.delete("/listings/{listing_id}", status_code=204)
def delete_listing(
    listing_id: int = ListingId,
    user: dict = Depends(get_current_user),
    listings: ListingRepository = Depends(get_listing_repository),
    store: ListingPhotoStore = Depends(get_listing_photo_store),
):
    """Delete your listing (admins can delete any). Its photos and
    conversations go with it."""
    listing = _own_listing(listing_id, user, listings, allow_admin=True)
    listings.delete(listing_id)
    for url in listing.get("photos") or []:
        store.remove_url(url)
    return Response(status_code=204)


@router.post(
    "/listings/photos",
    status_code=201,
    responses={413: {"description": "File over 4 MB"}, 422: {"description": "Not a PNG, JPEG or WebP picture"}},
)
def upload_listing_photo(
    file: UploadFile = File(description="A PNG, JPEG or WebP photo, up to 4 MB."),
    user: dict = Depends(get_current_user),
    store: ListingPhotoStore = Depends(get_listing_photo_store),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Upload one photo for a listing. It's checked, resized to at most
    1600 px, stripped of camera data and stored as WebP. Attach the returned
    URL to a listing within the same account."""
    enforce_rate_limit(limiter, f"listing-photo:{user['id']}", *PHOTO_UPLOADS,
                       "That's a lot of photos this hour. Try again later.")
    data = file.file.read(images.MAX_UPLOAD_BYTES + 1)
    try:
        webp = images.to_webp(data, max_side=PHOTO_MAX_SIDE, effort=3)
    except images.ImageTooLargeError:
        raise HTTPException(status_code=413, detail="Each photo must be 4 MB or smaller.")
    except images.InvalidImageError:
        raise HTTPException(status_code=422, detail="Upload a PNG, JPEG or WebP photo.")
    url = store.upload(f"u{user['id']}-{secrets.token_hex(10)}.webp", webp)
    return {"url": url}


# ---------- messages ----------

def _participant(conversation: dict | None, user: dict) -> dict:
    """The conversation, if this account is in it; otherwise 404 (not 403,
    so outsiders can't tell which conversations exist)."""
    if conversation is None or int(user["id"]) not in (int(conversation["buyer_id"]), int(conversation["seller_id"])):
        raise HTTPException(status_code=404, detail=CONVERSATION_NOT_FOUND)
    return conversation


def _side(conversation: dict, user: dict) -> str:
    return "buyer" if int(conversation["buyer_id"]) == int(user["id"]) else "seller"


def _unread(conversation: dict, user: dict) -> bool:
    """A message from the other side that this account hasn't opened yet."""
    sender = conversation.get("last_sender_id")
    if sender is None or int(sender) == int(user["id"]):
        return False
    read_at = conversation.get(f"{_side(conversation, user)}_read_at")
    return read_at is None or str(read_at) < str(conversation["last_message_at"])


def _conversation_summaries(rows: list[dict], user: dict, listings: ListingRepository,
                            users: UserRepository) -> list[dict]:
    by_listing = {}
    for listing_id in {r["listing_id"] for r in rows}:
        listing = listings.get(listing_id)
        if listing:
            by_listing[listing_id] = listing
    other_ids = [r["seller_id"] if _side(r, user) == "buyer" else r["buyer_id"] for r in rows]
    emails = users.emails(other_ids)
    out = []
    for row, other in zip(rows, other_ids):
        listing = by_listing.get(row["listing_id"]) or {}
        photos = listing.get("photos") or []
        out.append({
            "id": row["id"],
            "role": "buying" if _side(row, user) == "buyer" else "selling",
            "with": {"id": other, "name": _name(emails.get(int(other)))},
            "listing": {
                "id": row["listing_id"],
                "title": listing.get("title", "Deleted listing"),
                "price": float(listing["price"]) if listing.get("price") is not None else None,
                "currency": listing.get("currency"),
                "status": listing.get("status"),
                "cover": photos[0] if photos else None,
            },
            "last_body": row.get("last_body", ""),
            "last_message_at": row.get("last_message_at"),
            "last_from_me": int(row.get("last_sender_id") or 0) == int(user["id"]),
            "unread": _unread(row, user),
        })
    return out


def _post(conversation: dict, user: dict, text: str, conversations: ConversationRepository,
          messages: MessageRepository) -> dict:
    message = messages.add(conversation["id"], user["id"], text)
    # "Read" and "last message" times both come from the API's clock, so the
    # unread check never compares two different clocks.
    now = _now()
    conversations.update(conversation["id"], {
        "last_message_at": now,
        "last_sender_id": user["id"],
        "last_body": text[:2000],
        f"{_side(conversation, user)}_read_at": now,
    })
    return message


@router.post("/listings/{listing_id}/messages", status_code=201)
def message_seller(
    body: MessageIn,
    listing_id: int = ListingId,
    user: dict = Depends(get_current_user),
    listings: ListingRepository = Depends(get_listing_repository),
    conversations: ConversationRepository = Depends(get_conversation_repository),
    messages: MessageRepository = Depends(get_message_repository),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Send the seller a message about their listing. The first one starts a
    conversation; later ones continue it. Returns the conversation's ID."""
    enforce_rate_limit(limiter, f"message:{user['id']}", *NEW_MESSAGES,
                       "You're sending messages very fast. Wait a few minutes.")
    listing = listings.get(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail=LISTING_NOT_FOUND)
    if int(listing["seller_id"]) == int(user["id"]):
        raise HTTPException(status_code=409, detail="This is your own listing.")
    conversation = conversations.find(listing_id, user["id"])
    if conversation is None:
        if listing["status"] != "active":
            raise HTTPException(status_code=409, detail="This GPU has been sold.")
        conversation = conversations.create({
            "listing_id": listing_id, "buyer_id": user["id"], "seller_id": listing["seller_id"],
        })
    _post(conversation, user, body.body, conversations, messages)
    return {"conversation_id": conversation["id"]}


@router.get("/me/conversations")
def my_conversations(
    user: dict = Depends(get_current_user),
    listings: ListingRepository = Depends(get_listing_repository),
    conversations: ConversationRepository = Depends(get_conversation_repository),
    users: UserRepository = Depends(get_user_repository),
):
    """Your inbox: conversations as buyer and seller, newest message first."""
    rows = conversations.for_user(user["id"])
    summaries = _conversation_summaries(rows, user, listings, users)
    return {"unread": sum(1 for s in summaries if s["unread"]), "conversations": summaries}


@router.get("/me/unread")
def my_unread(
    user: dict = Depends(get_current_user),
    conversations: ConversationRepository = Depends(get_conversation_repository),
):
    """How many conversations have a message you haven't opened (for the badge)."""
    return {"unread": sum(1 for row in conversations.for_user(user["id"]) if _unread(row, user))}


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int = ConversationId,
    user: dict = Depends(get_current_user),
    listings: ListingRepository = Depends(get_listing_repository),
    conversations: ConversationRepository = Depends(get_conversation_repository),
    messages: MessageRepository = Depends(get_message_repository),
    users: UserRepository = Depends(get_user_repository),
):
    """One conversation and its messages. Opening it marks it read."""
    conversation = _participant(conversations.get(conversation_id), user)
    rows = messages.list(conversation_id)
    conversations.update(conversation_id, {f"{_side(conversation, user)}_read_at": _now()})
    summary = _conversation_summaries([conversation], user, listings, users)[0]
    summary["unread"] = False
    return {
        **summary,
        "messages": [{
            "id": m["id"],
            "body": m["body"],
            "created_at": m["created_at"],
            "mine": int(m["sender_id"]) == int(user["id"]),
        } for m in rows],
    }


@router.post("/conversations/{conversation_id}/messages", status_code=201)
def reply(
    body: MessageIn,
    conversation_id: int = ConversationId,
    user: dict = Depends(get_current_user),
    conversations: ConversationRepository = Depends(get_conversation_repository),
    messages: MessageRepository = Depends(get_message_repository),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    """Reply in a conversation you're part of."""
    enforce_rate_limit(limiter, f"message:{user['id']}", *NEW_MESSAGES,
                       "You're sending messages very fast. Wait a few minutes.")
    conversation = _participant(conversations.get(conversation_id), user)
    message = _post(conversation, user, body.body, conversations, messages)
    return {"id": message["id"], "body": message["body"], "created_at": message.get("created_at"), "mine": True}
