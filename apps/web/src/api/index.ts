import type {ApiClient} from "./client";
import {httpClient} from "./httpClient";
import {mockClient} from "./mockClient";

// The one-line switch: change mockClient to httpClient when the API is ready.
export const api: ApiClient = mockClient;

export * from "./types";
export type {ApiClient} from "./client";
