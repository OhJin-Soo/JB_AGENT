from app.schemas.analysis import CashflowItem


SEASONAL_KEYWORDS = {"전기", "전기요금", "난방", "냉방", "관리비", "utility", "utilities"}
FIXED_KEYWORDS = {"월급", "급여", "연금", "보험", "월세", "salary", "pension", "rent"}


def select_model(item: CashflowItem) -> str:
    category = item.category.lower()
    description = (item.description or "").lower()
    text = f"{category} {description}"
    if any(keyword in text for keyword in SEASONAL_KEYWORDS):
        return "sarimax"
    if any(keyword in text for keyword in FIXED_KEYWORDS):
        return "rule_based"
    return "xgboost"
