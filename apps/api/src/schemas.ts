import { z } from "zod";

const pagination = z.object({
  limit: z.coerce.number().int().min(1).max(200).default(50),
  offset: z.coerce.number().int().min(0).default(0),
});

export const signalQuery = pagination.extend({
  source: z.string().optional(),
  processed: z.enum(["true", "false"]).optional(),
});

export const eventQuery = pagination.extend({
  type: z.string().optional(),
});

export const searchQuery = z.object({
  q: z.string().min(1).max(200),
  limit: z.coerce.number().int().min(1).max(100).default(20),
});

export const companyQuery = pagination;
