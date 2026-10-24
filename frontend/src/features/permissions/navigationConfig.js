import { FARM_MODULES } from "./permissionCatalog";

const MODULE_ITEMS = Object.freeze(Object.values(FARM_MODULES).map((module) => Object.freeze({
  ...module,
  href: module.key === "farm" ? "/farm/details" : module.key === "staff" ? "/farm/staff" : module.key === "cattle" ? "/cattle" : module.key === "health" ? "/health" : module.key === "milk" ? "/milk" : module.key === "feed" ? "/feed" : module.key === "breeding" ? "/breeding" : module.key === "finance" ? "/finance" : module.key === "marketplace" ? "/marketplace" : module.key === "tasks" ? "/tasks" : `/farm/${module.key}`,
  comingSoon: !["farm", "staff", "cattle", "health", "milk", "feed", "breeding", "finance", "marketplace", "tasks"].includes(module.key),
})));

export function farmNavigationItems(can) {
  if (typeof can !== "function") return [];
  return MODULE_ITEMS.filter((item) => can(item.permission));
}

export function appNavigationItems(can) {
  const modules = farmNavigationItems(can).filter((item) => !item.comingSoon);
  const vaccination = typeof can === "function" && can("health.view")
    ? [{ key: "vaccinations", title: "Vaccinations", description: "Schedules, reminders and administration history", permission: "health.view", href: "/vaccinations", comingSoon: false }]
    : [];
  return [...modules, ...vaccination];
}

export function platformNavigationItems(user) {
  if (!user?.is_system_admin) return [];
  return [{key:"platform-backups",title:"Backup & Recovery",description:"Encrypted platform backups and isolated recovery tests.",href:"/admin/backups",comingSoon:false},{key:"marketplace-moderation",title:"Marketplace Moderation",description:"Review reported marketplace listings without farm-data bypass.",href:"/marketplace/moderation",comingSoon:false},{
    key: "breed-catalog", title: "Global Breed Catalog", description: "System administrator authority is verified by the backend.", comingSoon: true,
  }];
}

export function moduleForRoute(moduleKey) {
  return typeof moduleKey === "string" ? FARM_MODULES[moduleKey] || null : null;
}
