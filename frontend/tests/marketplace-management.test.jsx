import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { MarketplaceHomeScreen, SellerDashboardScreen, SellerListingsScreen } from "../src/features/marketplace/screens/MarketplaceScreens";
import { ThemeProvider } from "../src/theme/ThemeProvider";

let mockFarm;
jest.mock("../src/features/farms/context/FarmProvider",()=>({useFarm:()=>mockFarm}));
jest.mock("../src/features/auth/context/AuthProvider",()=>({useAuth:()=>({user:{id:"buyer",is_system_admin:false}})}));

const FARM="11111111-1111-4111-8111-111111111111";
const listing={id:"listing-1",title:"Healthy dairy cow",description:"Healthy productive dairy cow for a local buyer.",asking_price:"250000.00",currency:"PKR",location:"Lahore",status:"PUBLISHED",sex:"FEMALE",age_months:48,breed_name:"Sahiwal",photos:[],saved:false};
const api=(overrides={})=>({browse:jest.fn().mockResolvedValue({items:[listing],total:1,limit:20,offset:0}),metrics:jest.fn().mockResolvedValue({active_listings:1,inquiry_count:2,sold_listings:3,sales_total:"240000",currency:"PKR"}),sellerListings:jest.fn().mockResolvedValue([listing]),changeStatus:jest.fn().mockResolvedValue({...listing,status:"RESERVED"}),...overrides});
const mount=node=>render(<ThemeProvider persistPreference={false}>{node}</ThemeProvider>);

beforeEach(()=>{mockFarm={status:"ready",activeFarm:{id:FARM,name:"Test Farm"},can:jest.fn().mockReturnValue(true)};});

test("marketplace browse loads backend listings and opens detail",async()=>{const service=api(),open=jest.fn(),screen=mount(<MarketplaceHomeScreen api={service} onNavigate={jest.fn()} onOpen={open}/>);await waitFor(()=>expect(screen.getByText("Healthy dairy cow")).toBeTruthy());expect(service.browse).toHaveBeenCalledWith(expect.objectContaining({sort:"newest",limit:20}));fireEvent.press(screen.getByText("View listing"));expect(open).toHaveBeenCalledWith("listing-1");});

test("seller dashboard is farm scoped and navigates to creation",async()=>{const service=api(),navigate=jest.fn(),screen=mount(<SellerDashboardScreen api={service} onNavigate={navigate}/>);await waitFor(()=>expect(screen.getByText("PKR 240,000")).toBeTruthy());expect(service.metrics).toHaveBeenCalledWith(FARM,{currency:"PKR"});fireEvent.press(screen.getByText("Create listing"));expect(navigate).toHaveBeenCalledWith("/marketplace/create");});

test("seller can reserve a published listing",async()=>{const service=api(),screen=mount(<SellerListingsScreen api={service} onEdit={jest.fn()} onSale={jest.fn()}/>);await waitFor(()=>expect(screen.getByText("Healthy dairy cow")).toBeTruthy());fireEvent.press(screen.getByText("Reserve"));await waitFor(()=>expect(service.changeStatus).toHaveBeenCalledWith(FARM,"listing-1","reserve",expect.any(String)));});

test("worker without listing permission cannot open seller dashboard",()=>{mockFarm.can=jest.fn().mockReturnValue(false);const screen=mount(<SellerDashboardScreen api={api()} onNavigate={jest.fn()}/>);expect(screen.getByText("Access denied")).toBeTruthy();});
