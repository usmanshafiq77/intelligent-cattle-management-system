import { apiClient } from "./client";
import { apiRoutes } from "./routes";

const root = apiRoutes.finance.root;
export const financeApi = Object.freeze({
  dashboard: (farmId, query, options) => apiClient.get(root(farmId, "dashboard"), { ...options, query }),
  categories: (farmId, options) => apiClient.get(root(farmId, "categories"), options),
  listIncome: (farmId, query, options) => apiClient.get(root(farmId, "income"), { ...options, query }),
  createIncome: (farmId, payload, options) => apiClient.post(root(farmId, "income"), { ...options, json: payload }),
  listExpenses: (farmId, query, options) => apiClient.get(root(farmId, "expenses"), { ...options, query }),
  createExpense: (farmId, payload, options) => apiClient.post(root(farmId, "expenses"), { ...options, json: payload }),
  updateTransaction: (farmId, id, payload, options) => apiClient.patch(apiRoutes.finance.transaction(farmId, id), { ...options, json: payload }),
  postTransaction: (farmId, id, options) => apiClient.post(`${apiRoutes.finance.transaction(farmId, id)}/post`, options),
  adjustTransaction: (farmId, id, payload, options) => apiClient.post(`${apiRoutes.finance.transaction(farmId, id)}/adjustments`, { ...options, json: payload }),
  listPayments: (farmId, options) => apiClient.get(root(farmId, "payments"), options),
  createPayment: (farmId, payload, options) => apiClient.post(root(farmId, "payments"), { ...options, json: payload }),
  listMilkSales: (farmId, options) => apiClient.get(root(farmId, "milk-sales"), options),
  createMilkSale: (farmId, payload, options) => apiClient.post(root(farmId, "milk-sales"), { ...options, json: payload }),
  customerBalances: (farmId, query, options) => apiClient.get(root(farmId, "customers/balances"), { ...options, query }),
  listCattleTransactions: (farmId, query, options) => apiClient.get(root(farmId, "cattle-transactions"), { ...options, query }),
  createCattleTransaction: (farmId, payload, options) => apiClient.post(root(farmId, "cattle-transactions"), { ...options, json: payload }),
  listBudgets: (farmId, options) => apiClient.get(root(farmId, "budgets"), options),
  createBudget: (farmId, payload, options) => apiClient.post(root(farmId, "budgets"), { ...options, json: payload }),
  budgetComparison: (farmId, query, options) => apiClient.get(root(farmId, "budgets/comparison"), { ...options, query }),
  listAssets: (farmId, options) => apiClient.get(root(farmId, "assets"), options),
  createAsset: (farmId, payload, options) => apiClient.post(root(farmId, "assets"), { ...options, json: payload }),
  updateAsset: (farmId, id, payload, options) => apiClient.patch(apiRoutes.finance.asset(farmId, id), { ...options, json: payload }),
  createMaintenance: (farmId, id, payload, options) => apiClient.post(`${apiRoutes.finance.asset(farmId, id)}/maintenance`, { ...options, json: payload }),
  listMaintenance: (farmId, id, options) => apiClient.get(`${apiRoutes.finance.asset(farmId, id)}/maintenance`, options),
  report: (farmId, query, options) => apiClient.get(root(farmId, "reports/summary"), { ...options, query }),
  audit: (farmId, query, options) => apiClient.get(root(farmId, "audit"), { ...options, query }),
  exportUrl: (farmId) => root(farmId, "reports/export"),
  exportReport: (farmId, query, options) => apiClient.get(root(farmId, "reports/export"), { ...options, query, responseType: "blob", timeoutMs: 60000 }),
});
