import { FARM_MODULES } from "./permissionCatalog";

const MODULE_ITEMS = Object.freeze(Object.values(FARM_MODULES).map((module) => Object.freeze({
  ...module,
  href: module.key === "cattle" ? "/cattle" : module.key === "feed" ? "/feed" : module.key === "breeding" ? "/breeding" : module.key === "finance" ? "/finance" : module.key === "marketplace" ? "/marketplace" : `/farm/${module.key}`,
  comingSoon: !["staff", "cattle", "feed", "breeding", "finance", "marketplace"].includes(module.key),
})));

export function farmNavigationItems(can) {
  if (typeof can !== "function") return [];
  return MODULE_ITEMS.filter((item) => can(item.permission));
}

export function platformNavigationItems(user) {
  if (!user?.is_system_admin) return [];
  return [{key:"marketplace-moderation",title:"Marketplace Moderation",description:"Review reported marketplace listings without farm-data bypass.",href:"/marketplace/moderation",comingSoon:false},{
    key: "breed-catalog", title: "Global Breed Catalog", description: "System administrator authority is verified by the backend.", comingSoon: true,
  }];
}

export function moduleForRoute(moduleKey) {
  return typeof moduleKey === "string" ? FARM_MODULES[moduleKey] || null : null;
}
