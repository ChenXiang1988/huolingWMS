"""Menu management routes."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import _build_menu_tree, get_current_user, require_permission
from src.core.exceptions import NotFoundException, ValidationException, success_response
from src.core.i18n import t, get_locale
from src.crud import crud_menu
from src.db import get_db
from src.models import User
from src.schemas import MenuCreate, MenuUpdate

router = APIRouter(prefix="/menus", tags=["菜单管理"])


async def _validate_parent(
    db: AsyncSession,
    parent_id: int,
    menu_id: int | None = None,
    scope: Literal["admin", "owner"] | None = None,
) -> None:
    """Validate parent existence, hierarchy, and admin/owner scope consistency."""
    if parent_id == 0:
        if scope == "owner":
            raise ValidationException("货主门户菜单必须挂在「货主门户」目录下")
        return

    menus = await crud_menu.get_tree(db)
    by_id = {menu.id: menu for menu in menus}
    parent = by_id.get(parent_id)
    if parent is None:
        raise ValidationException(t("menu.parent_not_found"))
    if parent.type == "F":
        raise ValidationException(t("menu.button_cannot_be_parent"))
    if scope is not None and _is_owner_branch(parent, by_id) != (scope == "owner"):
        raise ValidationException("菜单父节点与当前端不一致，不能跨端移动")

    visited: set[int] = set()
    current_id = parent_id
    while current_id:
        if current_id == menu_id:
            raise ValidationException(t("menu.cannot_select_self_or_child"))
        if current_id in visited:
            raise ValidationException(t("menu.hierarchy_cycle"))
        visited.add(current_id)
        current = by_id.get(current_id)
        if current is None:
            raise ValidationException(t("menu.hierarchy_broken"))
        current_id = current.parent_id


def _is_owner_branch(menu, by_id: dict) -> bool:
    """判断菜单是否属于 /owner 子树（自身或任一祖先是 /owner 顶级目录）。"""
    seen = set()
    current = menu
    while current and current.id not in seen:
        if current.path == "/owner" and current.parent_id == 0:
            return True
        seen.add(current.id)
        current = by_id.get(current.parent_id)
    return False


def _filter_scope(menus, scope: Literal["admin", "owner"] | None):
    """按端过滤：owner 取 /owner 整支，admin 取其余分支；不传时全量。"""
    if scope is None:
        return menus
    by_id = {m.id: m for m in menus}
    return [
        m for m in menus
        if _is_owner_branch(m, by_id) == (scope == "owner")
    ]


@router.get("/tree")
async def menu_tree(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("system:menu:list"))],
    scope: Literal["admin", "owner"] | None = Query(None),
):
    """Get the menu tree; scope=admin|owner limits to one side's branch."""
    menus = await crud_menu.get_tree(db)
    tree = _build_menu_tree(_filter_scope(menus, scope))
    return success_response(data=tree)


@router.post("")
async def create_menu(
    body: MenuCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("system:menu:add"))],
):
    """Create a new menu item."""
    await _validate_parent(db, body.parent_id, scope=body.scope)
    new_menu = await crud_menu.create(db, body.model_dump(exclude={"scope"}))
    return success_response(data={"id": new_menu.id}, msg=t("menu.created"))


@router.put("/{menu_id}")
async def update_menu(
    menu_id: int,
    body: MenuUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("system:menu:edit"))],
):
    """Update a menu item."""
    existing = await crud_menu.get(db, menu_id)
    if not existing:
        raise NotFoundException(t("menu.not_found"))

    update_data = body.model_dump(exclude_unset=True, exclude={"scope"})
    if "parent_id" in update_data:
        # The frontend sends null when a clearable parent selector is emptied.
        # Persist root menus using the system-wide parent_id=0 convention.
        update_data["parent_id"] = update_data["parent_id"] or 0
        await _validate_parent(db, update_data["parent_id"], menu_id, scope=body.scope)

    updated = await crud_menu.update(db, menu_id, update_data)
    if not updated:
        raise NotFoundException(t("menu.not_found"))
    return success_response(msg=t("menu.updated"))


@router.delete("/{menu_id}")
async def delete_menu(
    menu_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permission("system:menu:delete"))],
):
    """Delete a menu item."""
    ok = await crud_menu.delete(db, menu_id, soft=False)
    if not ok:
        raise NotFoundException(t("menu.not_found"))
    return success_response(msg=t("menu.deleted"))
