"""People labels, nested groups, and communities a named manager can run."""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    AppNotification,
    Community,
    CommunityMember,
    CommunityPost,
    PeopleGroup,
    PeopleGroupMember,
    PollOption,
    PollVote,
    StudentProfile,
    User,
)
from app.security.auth import get_current_user, require_roles
from app.services.confirm import PhraseIn, require_phrase

router = APIRouter(prefix="/api/v1", tags=["people"])
Admins = require_roles("university_admin", "admin", "super_admin", "developer", "operator")
ADMIN_ROLES = {"university_admin", "admin", "super_admin", "developer", "operator"}


async def _people(db: AsyncSession, text: str) -> list[User]:
    keys = []
    for part in text.replace(",", "\n").splitlines():
        token = part.strip().casefold()
        if token and token not in keys:
            keys.append(token)
    if not keys:
        return []
    rows = (
        await db.execute(
            select(User)
            .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
            .where(or_(func.lower(User.username).in_(keys), func.lower(StudentProfile.student_id).in_(keys)))
            .options(selectinload(User.student))
        )
    ).scalars().unique().all()
    return list(rows)


def _label(user: User) -> str:
    register = user.student.student_id if user.student else ""
    return f"{user.full_name} · {register or user.username}"


class GroupIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    parent_id: Optional[int] = None
    purpose: str = ""


class IdentitiesIn(BaseModel):
    identities: str = ""
    group_id: Optional[int] = None


class CommunityIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    purpose: str = ""
    manager: str


class PostIn(BaseModel):
    kind: str = "message"
    title: str = ""
    body: str = ""
    link_url: str = ""
    options: str = ""


class VoteIn(BaseModel):
    option_id: int


@router.get("/admin/groups")
async def list_groups(_: Annotated[User, Depends(Admins)], db: Annotated[AsyncSession, Depends(get_db)]):
    groups = (await db.execute(select(PeopleGroup).order_by(PeopleGroup.id))).scalars().all()
    members = (await db.execute(select(PeopleGroupMember))).scalars().all()
    user_ids = {row.user_id for row in members}
    people = {}
    if user_ids:
        found = (await db.execute(select(User).where(User.id.in_(user_ids)).options(selectinload(User.student)))).scalars().all()
        people = {row.id: row for row in found}
    by_group: dict[int, list] = {}
    for row in members:
        person = people.get(row.user_id)
        by_group.setdefault(row.group_id, []).append(
            {"user_id": row.user_id, "label": _label(person) if person else str(row.user_id)}
        )
    return {
        "items": [
            {
                "id": group.id,
                "name": group.name,
                "parent_id": group.parent_id,
                "purpose": group.purpose,
                "members": by_group.get(group.id, []),
            }
            for group in groups
        ]
    }


@router.post("/admin/groups")
async def create_group(body: GroupIn, _: Annotated[User, Depends(Admins)], db: Annotated[AsyncSession, Depends(get_db)]):
    if body.parent_id:
        parent = (await db.execute(select(PeopleGroup).where(PeopleGroup.id == body.parent_id))).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent group not found")
    row = PeopleGroup(name=body.name.strip(), parent_id=body.parent_id, purpose=body.purpose.strip()[:200])
    db.add(row)
    await db.commit()
    return {"ok": True, "id": row.id}


@router.post("/admin/groups/{group_id}/members")
async def add_group_members(
    group_id: int,
    body: IdentitiesIn,
    _: Annotated[User, Depends(Admins)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    group = (await db.execute(select(PeopleGroup).where(PeopleGroup.id == group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    people = await _people(db, body.identities)
    if not people:
        raise HTTPException(status_code=404, detail="No matching register number or username")
    existing = {
        row
        for row in (
            await db.execute(select(PeopleGroupMember.user_id).where(PeopleGroupMember.group_id == group.id))
        ).scalars().all()
    }
    added = 0
    for person in people:
        if person.id in existing:
            continue
        db.add(PeopleGroupMember(group_id=group.id, user_id=person.id))
        added += 1
    await db.commit()
    return {"ok": True, "added": added}


@router.delete("/admin/groups/{group_id}")
async def delete_group(
    group_id: int,
    body: PhraseIn,
    _: Annotated[User, Depends(Admins)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    group = (await db.execute(select(PeopleGroup).where(PeopleGroup.id == group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    require_phrase(body.confirm, group.name)
    members = (await db.execute(select(PeopleGroupMember).where(PeopleGroupMember.group_id == group.id))).scalars().all()
    children = (await db.execute(select(PeopleGroup).where(PeopleGroup.parent_id == group.id))).scalars().all()
    for row in members:
        await db.delete(row)
    for child in children:
        child.parent_id = None
    await db.delete(group)
    await db.commit()
    return {"ok": True}


async def _community(db: AsyncSession, community_id: int) -> Community:
    row = (await db.execute(select(Community).where(Community.id == community_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Community not found")
    return row


def _can_manage(user: User, community: Community) -> bool:
    return user.role in ADMIN_ROLES or community.manager_id == user.id


async def _can_read(db: AsyncSession, user: User, community: Community) -> bool:
    if _can_manage(user, community):
        return True
    member = (
        await db.execute(
            select(CommunityMember).where(CommunityMember.community_id == community.id, CommunityMember.user_id == user.id)
        )
    ).scalar_one_or_none()
    return member is not None


@router.get("/communities")
async def my_communities(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(select(Community).order_by(Community.id.desc()))).scalars().all()
    member_ids = {
        row
        for row in (
            await db.execute(select(CommunityMember.community_id).where(CommunityMember.user_id == user.id))
        ).scalars().all()
    }
    visible = [row for row in rows if row.id in member_ids or _can_manage(user, row)]
    managers = {}
    manager_ids = {row.manager_id for row in visible if row.manager_id}
    if manager_ids:
        found = (await db.execute(select(User).where(User.id.in_(manager_ids)))).scalars().all()
        managers = {row.id: row.full_name for row in found}
    return {
        "items": [
            {
                "id": row.id,
                "name": row.name,
                "purpose": row.purpose,
                "manager": managers.get(row.manager_id, ""),
                "can_manage": _can_manage(user, row),
            }
            for row in visible
        ]
    }


@router.post("/admin/communities")
async def create_community(body: CommunityIn, user: Annotated[User, Depends(Admins)], db: Annotated[AsyncSession, Depends(get_db)]):
    managers = await _people(db, body.manager)
    if len(managers) != 1:
        raise HTTPException(status_code=400, detail="Name one manager by username or register number")
    row = Community(name=body.name.strip(), purpose=body.purpose.strip()[:300], manager_id=managers[0].id, created_by=user.id)
    db.add(row)
    await db.flush()
    db.add(CommunityMember(community_id=row.id, user_id=managers[0].id))
    db.add(
        AppNotification(
            user_id=managers[0].id,
            kind="community",
            title=row.name,
            body="You have been asked to manage this community.",
            link="/community",
        )
    )
    await db.commit()
    return {"ok": True, "id": row.id}


@router.post("/communities/{community_id}/members")
async def add_members(
    community_id: int,
    body: IdentitiesIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    community = await _community(db, community_id)
    if not _can_manage(user, community):
        raise HTTPException(status_code=403, detail="Only the allocated manager can add people")
    people = await _people(db, body.identities)
    if body.group_id:
        member_ids = (
            await db.execute(select(PeopleGroupMember.user_id).where(PeopleGroupMember.group_id == body.group_id))
        ).scalars().all()
        if member_ids:
            grouped = (await db.execute(select(User).where(User.id.in_(member_ids)))).scalars().all()
            people.extend(grouped)
    if not people:
        raise HTTPException(status_code=404, detail="No people matched")
    existing = {
        row
        for row in (
            await db.execute(select(CommunityMember.user_id).where(CommunityMember.community_id == community.id))
        ).scalars().all()
    }
    added = 0
    seen = set()
    for person in people:
        if person.id in existing or person.id in seen:
            continue
        seen.add(person.id)
        db.add(CommunityMember(community_id=community.id, user_id=person.id))
        db.add(
            AppNotification(
                user_id=person.id,
                kind="community",
                title=community.name,
                body="You have been added to this community.",
                link="/community",
            )
        )
        added += 1
    await db.commit()
    return {"ok": True, "added": added}


@router.get("/communities/{community_id}")
async def community_feed(community_id: int, user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    community = await _community(db, community_id)
    if not await _can_read(db, user, community):
        raise HTTPException(status_code=403, detail="You are not in this community")
    posts = (
        await db.execute(select(CommunityPost).where(CommunityPost.community_id == community.id).order_by(CommunityPost.id.desc()).limit(80))
    ).scalars().all()
    post_ids = [row.id for row in posts]
    options = []
    votes = []
    if post_ids:
        options = (await db.execute(select(PollOption).where(PollOption.post_id.in_(post_ids)))).scalars().all()
        votes = (await db.execute(select(PollVote).where(PollVote.post_id.in_(post_ids)))).scalars().all()
    authors = {}
    author_ids = {row.author_id for row in posts}
    if author_ids:
        found = (await db.execute(select(User).where(User.id.in_(author_ids)))).scalars().all()
        authors = {row.id: row.full_name for row in found}
    counts: dict[int, int] = {}
    mine: dict[int, int] = {}
    for vote in votes:
        counts[vote.option_id] = counts.get(vote.option_id, 0) + 1
        if vote.user_id == user.id:
            mine[vote.post_id] = vote.option_id
    by_post: dict[int, list] = {}
    for option in options:
        by_post.setdefault(option.post_id, []).append({"id": option.id, "label": option.label, "votes": counts.get(option.id, 0)})
    return {
        "id": community.id,
        "name": community.name,
        "purpose": community.purpose,
        "can_manage": _can_manage(user, community),
        "posts": [
            {
                "id": row.id,
                "kind": row.kind,
                "title": row.title,
                "body": row.body,
                "link_url": row.link_url,
                "author": authors.get(row.author_id, ""),
                "options": by_post.get(row.id, []),
                "my_vote": mine.get(row.id),
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
            for row in posts
        ],
    }


@router.post("/communities/{community_id}/posts")
async def create_post(
    community_id: int,
    body: PostIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    community = await _community(db, community_id)
    if not _can_manage(user, community):
        raise HTTPException(status_code=403, detail="Only the allocated manager can post")
    kind = body.kind if body.kind in {"message", "link", "document", "poll"} else "message"
    if kind in {"link", "document"} and not body.link_url.strip():
        raise HTTPException(status_code=400, detail="Add the link to the page or document")
    choices = [part.strip() for part in body.options.replace("\n", ",").split(",") if part.strip()][:8]
    if kind == "poll" and len(choices) < 2:
        raise HTTPException(status_code=400, detail="A poll needs at least two choices")
    post = CommunityPost(
        community_id=community.id,
        author_id=user.id,
        kind=kind,
        title=body.title.strip()[:160] or community.name,
        body=body.body.strip()[:4000],
        link_url=body.link_url.strip()[:500],
    )
    db.add(post)
    await db.flush()
    for choice in choices:
        db.add(PollOption(post_id=post.id, label=choice[:120]))
    members = (
        await db.execute(select(CommunityMember.user_id).where(CommunityMember.community_id == community.id))
    ).scalars().all()
    for member_id in members:
        if member_id == user.id:
            continue
        db.add(
            AppNotification(
                user_id=member_id,
                kind="community",
                title=post.title,
                body=f"{community.name}: {kind}",
                link="/community",
            )
        )
    await db.commit()
    return {"ok": True, "id": post.id}


@router.post("/communities/{community_id}/posts/{post_id}/vote")
async def vote(
    community_id: int,
    post_id: int,
    body: VoteIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    community = await _community(db, community_id)
    if not await _can_read(db, user, community):
        raise HTTPException(status_code=403, detail="You are not in this community")
    option = (
        await db.execute(select(PollOption).where(PollOption.id == body.option_id, PollOption.post_id == post_id))
    ).scalar_one_or_none()
    if not option:
        raise HTTPException(status_code=404, detail="Choice not found")
    existing = (
        await db.execute(select(PollVote).where(PollVote.post_id == post_id, PollVote.user_id == user.id))
    ).scalar_one_or_none()
    if existing:
        existing.option_id = option.id
    else:
        db.add(PollVote(post_id=post_id, option_id=option.id, user_id=user.id))
    await db.commit()
    return {"ok": True}
