import type {Profile, ProfilePage, SearchParams} from "./types";

// Everything the pages may ask the back end for. The mock and the real
// client both implement this, so the pages never know which one they use.
export interface ApiClient {
    searchProfiles(params: SearchParams): Promise<ProfilePage>;
    getProfile(id: string): Promise<Profile>;
}
