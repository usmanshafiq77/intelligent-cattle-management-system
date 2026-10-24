import { fireEvent, render, waitFor } from "@testing-library/react-native";

import {
  DailyFeedingRecordsScreen,
  FeedDashboardScreen,
  FeedInventoryScreen,
} from "../src/features/feed/screens/FeedScreens";
import { ThemeProvider } from "../src/theme/ThemeProvider";

let mockFarm;
jest.mock("../src/features/farms/context/FarmProvider", () => ({ useFarm: () => mockFarm }));

const FARM_ID = "11111111-1111-4111-8111-111111111111";
const ITEM_ID = "22222222-2222-4222-8222-222222222222";
const ITEM = Object.freeze({
  id: ITEM_ID,
  farm_id: FARM_ID,
  name: "Maize Silage",
  category: "FORAGE",
  unit: "KG",
  current_quantity: "80.000",
  reorder_level: "20.000",
  is_active: true,
});

function makeApi(overrides = {}) {
  return {
    listItems: jest.fn().mockResolvedValue([ITEM]),
    stockHistory: jest.fn().mockResolvedValue([]),
    lowStock: jest.fn().mockResolvedValue([]),
    listSchedules: jest.fn().mockResolvedValue([]),
    listConsumption: jest.fn().mockResolvedValue([]),
    listPurchases: jest.fn().mockResolvedValue([]),
    listNutritionPlans: jest.fn().mockResolvedValue([]),
    consumptionReport: jest.fn().mockResolvedValue({ consumption_records: 0, consumption_quantity_by_unit: {} }),
    costReport: jest.fn().mockResolvedValue({ purchase_count: 0, purchase_cost_by_currency: {} }),
    createItem: jest.fn().mockResolvedValue(ITEM),
    updateItem: jest.fn().mockResolvedValue(ITEM),
    adjustStock: jest.fn().mockResolvedValue({ id: "movement-id", resulting_quantity: "85.000" }),
    createConsumption: jest.fn().mockResolvedValue({ id: "record-id" }),
    ...overrides,
  };
}

function renderScreen(node) {
  return render(<ThemeProvider persistPreference={false}>{node}</ThemeProvider>);
}

beforeEach(() => {
  mockFarm = {
    status: "ready",
    activeFarm: { id: FARM_ID, name: "Green Valley" },
    can: jest.fn().mockReturnValue(true),
  };
});

test("feed dashboard loads farm-scoped inventory and alerts", async () => {
  const api = makeApi();
  const screen = renderScreen(<FeedDashboardScreen api={api} onNavigate={jest.fn()} />);

  await waitFor(() => expect(screen.getByText("Feed Items")).toBeTruthy());
  expect(api.listItems).toHaveBeenCalledWith(FARM_ID);
  expect(api.lowStock).toHaveBeenCalledWith(FARM_ID);
});

test("authorized inventory user validates and creates a feed item", async () => {
  const api = makeApi();
  const screen = renderScreen(<FeedInventoryScreen api={api} />);
  await waitFor(() => expect(screen.getByText("Maize Silage")).toBeTruthy());

  fireEvent.changeText(screen.getByTestId("feed-name"), "Mineral Mix");
  fireEvent.changeText(screen.getByTestId("feed-category"), "MINERAL");
  fireEvent.changeText(screen.getByTestId("feed-unit"), "KG");
  fireEvent.changeText(screen.getByTestId("feed-reorder"), "5");
  fireEvent.press(screen.getByTestId("feed-item-submit"));

  await waitFor(() => expect(api.createItem).toHaveBeenCalledWith(FARM_ID, expect.objectContaining({ name: "Mineral Mix", category: "MINERAL", unit: "KG", reorder_level: "5" })));

  fireEvent.changeText(screen.getByTestId("adjustment-item"), ITEM_ID);
  fireEvent.changeText(screen.getByTestId("adjustment-direction"), "IN");
  fireEvent.changeText(screen.getByTestId("adjustment-quantity"), "5");
  fireEvent.changeText(screen.getByTestId("adjustment-reason"), "Verified physical count");
  fireEvent.press(screen.getByTestId("adjustment-submit"));
  await waitFor(() => expect(api.adjustStock).toHaveBeenCalledWith(FARM_ID, expect.objectContaining({ feed_item_id: ITEM_ID, direction: "IN", quantity: "5", unit: "KG", reason: "Verified physical count" })));
});

test("worker can record feeding without receiving inventory management controls", async () => {
  mockFarm.can = jest.fn((permission) => ["feed.view", "feed.record"].includes(permission));
  const api = makeApi();
  const screen = renderScreen(<DailyFeedingRecordsScreen api={api} />);
  await waitFor(() => expect(screen.getByTestId("feeding-item")).toBeTruthy());

  fireEvent.changeText(screen.getByTestId("feeding-item"), ITEM_ID);
  fireEvent.changeText(screen.getByLabelText("Cattle group"), "Lactating cows");
  fireEvent.changeText(screen.getByLabelText("Head count"), "10");
  fireEvent.changeText(screen.getByTestId("feeding-quantity"), "25");
  fireEvent.press(screen.getByTestId("feeding-submit"));

  await waitFor(() => expect(api.createConsumption).toHaveBeenCalledWith(FARM_ID, expect.objectContaining({ feed_item_id: ITEM_ID, group_name: "Lactating cows", head_count: 10, quantity: "25", unit: "KG" })));
  expect(mockFarm.can).toHaveBeenCalledWith("feed.record");
});
