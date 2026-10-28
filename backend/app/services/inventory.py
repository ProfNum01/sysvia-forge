from sqlalchemy import func, select
from backend.app.models.database import CorrectiveAction, Inventory


def available_quantity(db, product_id):
    inventory = db.scalar(select(Inventory).where(Inventory.product_id == product_id))
    if inventory is None:
        return 0
    reserved = db.scalar(select(func.coalesce(func.sum(CorrectiveAction.quantity), 0)).where(
        CorrectiveAction.type == "CREATE_PICKING_TASK",
        CorrectiveAction.status == "EXECUTED", CorrectiveAction.product_id == product_id))
    return max(0, inventory.quantity_available - reserved)
