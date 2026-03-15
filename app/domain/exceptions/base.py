"""Base domain exceptions."""

from __future__ import annotations


class DomainException(Exception):
    """Base exception for all domain errors."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class EntityNotFoundException(DomainException):
    """Raised when a requested entity is not found."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(
            message=f"{entity_type} with id '{entity_id}' not found",
            code="ENTITY_NOT_FOUND",
        )


class ValidationException(DomainException):
    """Raised when domain validation fails."""

    def __init__(self, field: str, detail: str) -> None:
        self.field = field
        self.detail = detail
        super().__init__(
            message=f"Validation failed for '{field}': {detail}",
            code="VALIDATION_ERROR",
        )


class BusinessRuleViolation(DomainException):
    """Raised when a business rule is violated."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(
            message=f"Business rule violated: {rule}",
            code="BUSINESS_RULE_VIOLATION",
        )
