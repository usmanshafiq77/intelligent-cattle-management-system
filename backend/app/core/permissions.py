from enum import StrEnum


class Permission(StrEnum):
    FARM_VIEW = "farm.view"
    FARM_MANAGE = "farm.manage"
    STAFF_VIEW = "staff.view"
    STAFF_MANAGE = "staff.manage"
    ROLES_MANAGE = "roles.manage"
    CATTLE_VIEW = "cattle.view"
    CATTLE_CREATE = "cattle.create"
    CATTLE_UPDATE = "cattle.update"
    CATTLE_DELETE = "cattle.delete"
    HEALTH_VIEW = "health.view"
    HEALTH_MANAGE = "health.manage"
    HEALTH_CREATE = "health.create"
    HEALTH_DIAGNOSIS = "health.diagnosis"
    HEALTH_VACCINATION_MANAGE = "health.vaccination.manage"
    HEALTH_VACCINATION_ADMINISTER = "health.vaccination.administer"
    HEALTH_TREATMENT_MANAGE = "health.treatment.manage"
    HEALTH_MEDICATION_ADMINISTER = "health.medication.administer"
    HEALTH_VISIT_MANAGE = "health.visit.manage"
    HEALTH_AUDIT_VIEW = "health.audit.view"
    MILK_VIEW = "milk.view"
    MILK_RECORD = "milk.record"
    MILK_MANAGE = "milk.manage"
    FEED_VIEW = "feed.view"
    FEED_MANAGE = "feed.manage"
    BREEDING_VIEW = "breeding.view"
    BREEDING_MANAGE = "breeding.manage"
    FINANCE_VIEW = "finance.view"
    FINANCE_MANAGE = "finance.manage"
    SALARY_VIEW = "salary.view"
    SALARY_MANAGE = "salary.manage"
    REPORTS_VIEW = "reports.view"
    REPORTS_EXPORT = "reports.export"


PERMISSION_CATALOG = frozenset(Permission)
PERMISSION_CODES = frozenset(permission.value for permission in Permission)
