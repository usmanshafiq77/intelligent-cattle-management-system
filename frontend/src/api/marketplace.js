import { apiClient, DEFAULT_UPLOAD_TIMEOUT_MS } from "./client";
import { apiRoutes } from "./routes";

const routes=apiRoutes.marketplace;
export const marketplaceApi=Object.freeze({
  browse:(query,options)=>apiClient.get(routes.listings,{...options,query}),
  detail:(id,options)=>apiClient.get(routes.listing(id),options),
  createInquiry:(id,payload,options)=>apiClient.post(`${routes.listing(id)}/inquiries`,{...options,json:payload}),
  buyerInquiries:(query,options)=>apiClient.get(routes.buyerInquiries,{...options,query}),
  inquiry:(id,options)=>apiClient.get(routes.inquiry(id),options),
  sendMessage:(id,payload,options)=>apiClient.post(`${routes.inquiry(id)}/messages`,{...options,json:payload}),
  closeInquiry:(id,options)=>apiClient.post(`${routes.inquiry(id)}/close`,options),
  reopenInquiry:(id,options)=>apiClient.post(`${routes.inquiry(id)}/reopen`,options),
  save:(id,options)=>apiClient.post(`${routes.listing(id)}/favorite`,options),
  unsave:(id,options)=>apiClient.delete(`${routes.listing(id)}/favorite`,options),
  saved:(options)=>apiClient.get(routes.saved,options),
  report:(id,payload,options)=>apiClient.post(`${routes.listing(id)}/reports`,{...options,json:payload}),
  notifications:(query,options)=>apiClient.get(routes.notifications,{...options,query}),
  readNotification:(id,options)=>apiClient.post(`${routes.notifications}/${encodeURIComponent(id)}/read`,options),
  sellerListings:(farmId,query,options)=>apiClient.get(routes.sellerRoot(farmId,"listings"),{...options,query}),
  createListing:(farmId,payload,options)=>apiClient.post(routes.sellerRoot(farmId,"listings"),{...options,json:payload}),
  updateListing:(farmId,id,payload,options)=>apiClient.patch(routes.sellerListing(farmId,id),{...options,json:payload}),
  changeStatus:(farmId,id,action,reason,options)=>apiClient.post(`${routes.sellerListing(farmId,id)}/${action}`,{...options,json:{reason:reason||null}}),
  uploadPhoto:(farmId,id,{filename,bytes,contentType,isPrimary=false},options)=>apiClient.post(`${routes.sellerListing(farmId,id)}/photos`,{...options,query:{filename,is_primary:isPrimary},body:bytes,headers:{"Content-Type":contentType},timeoutMs:DEFAULT_UPLOAD_TIMEOUT_MS}),
  setPrimaryPhoto:(farmId,id,photoId,options)=>apiClient.post(`${routes.sellerListing(farmId,id)}/photos/${encodeURIComponent(photoId)}/primary`,options),
  removePhoto:(farmId,id,photoId,options)=>apiClient.delete(`${routes.sellerListing(farmId,id)}/photos/${encodeURIComponent(photoId)}`,options),
  sellerInquiries:(farmId,query,options)=>apiClient.get(routes.sellerRoot(farmId,"inquiries"),{...options,query}),
  completeSale:(farmId,id,payload,options)=>apiClient.post(`${routes.sellerListing(farmId,id)}/sales`,{...options,json:payload}),
  metrics:(farmId,query,options)=>apiClient.get(routes.sellerRoot(farmId,"reports"),{...options,query}),
  audit:(farmId,query,options)=>apiClient.get(routes.sellerRoot(farmId,"audit"),{...options,query}),
  moderationReports:(query,options)=>apiClient.get(routes.moderationReports,{...options,query}),
  moderate:(id,payload,options)=>apiClient.post(`/marketplace/moderation/listings/${encodeURIComponent(id)}`,{...options,json:payload}),
});
