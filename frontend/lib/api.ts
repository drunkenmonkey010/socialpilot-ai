const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type User = {
  id: number;
  email: string;
  username?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Brand = { id:number; user_id:number; name:string; description:string|null; website_url:string|null; created_at:string; updated_at:string };
export type Campaign = { id:number; brand_id:number; name:string; description:string|null; status:string; created_at:string; updated_at:string };
export type PostStatus = "draft"|"pending_review"|"approved"|"rejected"|"scheduled"|"publishing"|"published"|"failed";
export type Post = { id:number; campaign_id:number; content:string; platform:string; status:PostStatus; scheduled_at:string|null; published_at:string|null; created_at:string; updated_at:string };
export type SocialAccount = { id:number; user_id:number; platform:string; account_name:string; account_id:string; token_expires_at:string|null; is_active:boolean; created_at:string; updated_at:string };
export type LoginResponse = { access_token:string; token_type:string };
export type DashboardStats = { drafts:number; needs_review:number; scheduled:number; published:number };
export type DashboardWorkspace = { name:string; brand_count:number };
export type DashboardUpcomingPost = { id:number; content:string; platform:string; scheduled_at:string; campaign_name:string };
export type DashboardReviewPost = { id:number; content:string; platform:string; created_at:string; campaign_name:string };
export type DashboardOverview = { user:User; workspace:DashboardWorkspace; stats:DashboardStats; upcoming:DashboardUpcomingPost[]; needs_review:DashboardReviewPost[]; connected_accounts:number };

type ApiErrorBody = { error?:{code?:string;message?:string}; detail?:string; message?:string };
export class ApiError extends Error { status:number; code?:string; constructor(message:string,status:number,code?:string){super(message);this.name="ApiError";this.status=status;this.code=code;} }

async function request<T>(path:string, options:RequestInit={}, token?:string|null):Promise<T>{
  const headers=new Headers(options.headers);
  if(options.body && !headers.has("Content-Type")) headers.set("Content-Type","application/json");
  if(token) headers.set("Authorization",`Bearer ${token}`);
  let response:Response;
  try { response=await fetch(`${API_URL}${path}`,{...options,headers,cache:"no-store"}); }
  catch { throw new ApiError("Unable to connect to SocialPilot. Please make sure the backend is running.",0); }
  if(!response.ok){let body:ApiErrorBody|null=null;try{body=await response.json();}catch{};const message=body?.error?.message||body?.detail||body?.message||`Request failed with status ${response.status}`;throw new ApiError(message,response.status,body?.error?.code);}
  if(response.status===204)return undefined as T;
  return await response.json() as T;
}

export const login=(email:string,password:string)=>request<LoginResponse>("/auth/login",{method:"POST",body:JSON.stringify({email,password})});
export const getCurrentUser=(token:string)=>request<User>("/auth/me",{},token);
export const getDashboardOverview=(token:string)=>request<DashboardOverview>("/dashboard/overview",{},token);
export const getBrands=(token:string)=>request<Brand[]>("/brands",{},token);
export const getBrandCampaigns=(token:string,brandId:number)=>request<Campaign[]>(`/campaigns/brand/${brandId}`,{},token);
export const getCampaignPosts=(token:string,campaignId:number)=>request<Post[]>(`/posts/campaign/${campaignId}`,{},token);
export const getSocialAccounts=(token:string)=>request<SocialAccount[]>("/social-accounts",{},token);
export const createCampaign=(token:string,data:{brand_id:number;name:string;description?:string|null;status?:string})=>request<Campaign>("/campaigns",{method:"POST",body:JSON.stringify({brand_id:data.brand_id,name:data.name,description:data.description??null,status:data.status??"draft"})},token);
export const updateCampaign=(token:string,id:number,data:{name?:string;description?:string|null;status?:string})=>request<Campaign>(`/campaigns/${id}`,{method:"PATCH",body:JSON.stringify(data)},token);
export const deleteCampaign=(token:string,id:number)=>request<void>(`/campaigns/${id}`,{method:"DELETE"},token);
export const generateCampaignPost=(token:string,id:number,platform:string)=>request<Post>(`/campaigns/${id}/generate-post?${new URLSearchParams({platform})}`,{method:"POST"},token);
export const createPost=(token:string,data:{campaign_id:number;content:string;platform:string;scheduled_at?:string|null})=>request<Post>("/posts",{method:"POST",body:JSON.stringify(data)},token);
export const updatePost=(token:string,id:number,data:{content?:string;platform?:string;scheduled_at?:string|null})=>request<Post>(`/posts/${id}`,{method:"PATCH",body:JSON.stringify(data)},token);
export const submitPostForReview=(token:string,id:number)=>request<Post>(`/posts/${id}/submit-review`,{method:"POST"},token);
export const approvePost=(token:string,id:number)=>request<Post>(`/posts/${id}/approve`,{method:"POST"},token);
export const rejectPost=(token:string,id:number)=>request<Post>(`/posts/${id}/reject`,{method:"POST"},token);
export const schedulePost=(token:string,id:number,scheduledAt:string)=>request<Post>(`/posts/${id}/schedule`,{method:"POST",body:JSON.stringify({scheduled_at:scheduledAt})},token);
export const publishPost=(token:string,id:number)=>request<Post>(`/posts/${id}/publish`,{method:"POST"},token);
export const deletePost=(token:string,id:number)=>request<void>(`/posts/${id}`,{method:"DELETE"},token);
