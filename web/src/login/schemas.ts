import { z } from "zod";

// Mirrors the server rules (the server is still the authority).
const email = z.string().trim().toLowerCase().email("Enter a valid email address").max(254);
const password = z
  .string()
  .min(8, "At least 8 characters")
  .refine((v) => new TextEncoder().encode(v).length <= 72, "At most 72 bytes");

export const loginSchema = z.object({ email: z.string().trim().min(1, "Enter your email"), password: z.string().min(1, "Enter your password") });
export const registerSchema = z.object({
  display_name: z.string().trim().min(1, "Enter your name").max(40, "At most 40 characters"),
  email,
  password,
  language: z.string().min(1),
  accept_privacy: z.boolean().refine((v) => v, "You need to accept the privacy policy to create an account"),
});
export type LoginValues = z.infer<typeof loginSchema>;
export type RegisterValues = z.infer<typeof registerSchema>;
