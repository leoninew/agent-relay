from fastapi import APIRouter

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/exception")
def throw_diagnostic_exception() -> None:
    raise RuntimeError("This diagnostic endpoint intentionally throws.")
