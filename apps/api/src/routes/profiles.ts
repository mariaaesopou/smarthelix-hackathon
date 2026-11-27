import type { FastifyInstance } from "fastify";
import { createProfileController } from "../controllers/profiles.ts";
import {
  DEFAULT_PER_PAGE, DEFAULT_RECOMMENDATIONS, MAX_PER_PAGE, MAX_RECOMMENDATIONS, type ProfileService,
} from "../services/profiles.ts";

const filterText = { type: "string", minLength: 1, maxLength: 200 } as const;
const errorResponse = { $ref: "error.json#" } as const;

const listSchema = {
  summary: "Search profiles",
  querystring: {
    type: "object",
    properties: {
      q: { type: "string", maxLength: 200, description: "Words to find in name, skills, services and description (Greek or English)" },
      type: { type: "string", enum: ["sme", "young_entrepreneur", "freelancer"] },
      sector: filterText,
      region: filterText,
      skill: filterText,
      source: filterText,
      page: { type: "integer", minimum: 1, default: 1 },
      per_page: { type: "integer", minimum: 1, maximum: MAX_PER_PAGE, default: DEFAULT_PER_PAGE },
    },
  },
  response: { 200: { $ref: "profile-page.json#" }, 400: errorResponse },
} as const;

const idParams = {
  type: "object",
  required: ["id"],
  properties: { id: { type: "string", format: "uuid" } },
} as const;

const getSchema = {
  summary: "Get one profile",
  params: idParams,
  response: { 200: { $ref: "profile.json#" }, 400: errorResponse, 404: errorResponse },
} as const;

const recommendationSchema = (summary: string) => ({
  summary,
  params: idParams,
  querystring: {
    type: "object",
    properties: {
      limit: { type: "integer", minimum: 1, maximum: MAX_RECOMMENDATIONS, default: DEFAULT_RECOMMENDATIONS },
    },
  },
  response: {
    200: { type: "array", items: { $ref: "recommendation.json#" } },
    400: errorResponse,
    404: errorResponse,
  },
} as const);

export function profileRoutes(service: ProfileService) {
  const controller = createProfileController(service);
  return async function register(app: FastifyInstance) {
    app.get("/profiles", { schema: listSchema }, controller.list);
    app.get("/profiles/:id", { schema: getSchema }, controller.get);
    app.get("/profiles/:id/similar",
      { schema: recommendationSchema("Similar profiles, from the current similarity run") },
      controller.similar);
    app.get("/profiles/:id/partners",
      { schema: recommendationSchema("Potential partners, from the current matching run") },
      controller.partners);
  };
}
