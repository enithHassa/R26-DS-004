import { useState } from "react";
import type { ChangeEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CheckCircle2, Loader2, UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { signup } from "../api/auth";
import { useUserSessionStore } from "../store/user-session-store";

const MAX_PICTURE_BYTES = 1_500_000;

const accountSchema = z
  .object({
    first_name: z.string().min(1, "Required").max(100),
    last_name: z.string().min(1, "Required").max(100),
    email: z.string().min(3, "Required").email("Enter a valid email"),
    mobile_number: z.string().min(5, "Required").max(32),
    country: z.string().min(1, "Required").max(100),
    date_of_birth: z.string().min(1, "Required"),
    gender: z.enum(["male", "female", "other"], { errorMap: () => ({ message: "Required" }) }),
    address: z.string().min(1, "Required").max(255),
    city: z.string().min(1, "Required").max(100),
    postal_code: z.string().min(1, "Required").max(20),
    profile_picture: z.string().optional().or(z.literal("")),
    password: z.string().min(6, "At least 6 characters"),
    confirm_password: z.string().min(1, "Required"),
  })
  .refine((v) => v.password === v.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  });

type AccountForm = z.infer<typeof accountSchema>;

const defaultValues: AccountForm = {
  first_name: "",
  last_name: "",
  email: "",
  mobile_number: "",
  country: "",
  date_of_birth: "",
  gender: "" as AccountForm["gender"],
  address: "",
  city: "",
  postal_code: "",
  profile_picture: "",
  password: "",
  confirm_password: "",
};

const DOT_GRID_BG =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40'%3E%3Ccircle cx='2' cy='2' r='1.4' fill='white' fill-opacity='0.14'/%3E%3C/svg%3E";

export function CreateAccountPage() {
  const navigate = useNavigate();
  const isAuthenticated = useUserSessionStore((s) => s.isAuthenticated);
  const role = useUserSessionStore((s) => s.role);
  const profileId = useUserSessionStore((s) => s.profileId);
  const [showSuccess, setShowSuccess] = useState(false);
  const [pictureError, setPictureError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<AccountForm>({
    resolver: zodResolver(accountSchema),
    defaultValues,
  });

  const picturePreview = watch("profile_picture");

  const signupMutation = useMutation({
    mutationFn: (values: AccountForm) =>
      signup({
        first_name: values.first_name,
        last_name: values.last_name,
        email: values.email,
        mobile_number: values.mobile_number,
        country: values.country,
        date_of_birth: values.date_of_birth,
        gender: values.gender,
        address: values.address,
        city: values.city,
        postal_code: values.postal_code,
        profile_picture: values.profile_picture || null,
        password: values.password,
        confirm_password: values.confirm_password,
      }),
    onSuccess: () => setShowSuccess(true),
  });

  if (isAuthenticated) {
    return (
      <Navigate
        to={role === "auditor" ? "/" : profileId ? "/portal" : "/portal/financial-intake"}
        replace
      />
    );
  }

  const onPictureChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      setValue("profile_picture", "");
      return;
    }
    if (file.size > MAX_PICTURE_BYTES) {
      setPictureError("Image is too large (max 1.5 MB).");
      return;
    }
    setPictureError(null);
    const reader = new FileReader();
    reader.onload = () => setValue("profile_picture", String(reader.result ?? ""));
    reader.readAsDataURL(file);
  };

  const onSubmit = (values: AccountForm) => signupMutation.mutate(values);

  return (
    <div
      className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10"
      style={{
        background:
          "radial-gradient(1200px circle at 15% 20%, color-mix(in srgb, var(--tax-accent) 55%, transparent) 0%, transparent 42%)," +
          "radial-gradient(1000px circle at 85% 75%, color-mix(in srgb, var(--primary) 65%, transparent) 0%, transparent 50%)," +
          "radial-gradient(800px circle at 50% 100%, color-mix(in srgb, var(--tax-accent) 30%, transparent) 0%, transparent 55%)," +
          "linear-gradient(160deg, #241419 0%, #150d10 55%, #1b1013 100%)",
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{ backgroundImage: `url("${DOT_GRID_BG}")`, backgroundSize: "40px 40px" }}
        aria-hidden
      />

      <div className="relative z-10 flex w-full max-w-2xl flex-col items-center">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 shadow-lg ring-1 ring-white/20 backdrop-blur-sm">
            <UserPlus className="h-7 w-7 text-white" />
          </div>
          <div className="text-lg font-semibold tracking-tight text-white">AI Tax Advisory</div>
          <div className="text-xs text-white/60">Create your account</div>
        </div>

        <Card className="w-full border-white/10 bg-white/95 shadow-2xl backdrop-blur-md">
          <form onSubmit={handleSubmit(onSubmit)}>
            <CardHeader>
              <CardTitle>Create account</CardTitle>
              <CardDescription>Tell us a bit about yourself to get started.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <Field label="First name" error={errors.first_name?.message}>
                <Input {...register("first_name")} autoComplete="given-name" />
              </Field>
              <Field label="Last name" error={errors.last_name?.message}>
                <Input {...register("last_name")} autoComplete="family-name" />
              </Field>
              <Field label="Email address" error={errors.email?.message}>
                <Input type="email" {...register("email")} autoComplete="email" />
              </Field>
              <Field label="Mobile number" error={errors.mobile_number?.message}>
                <Input type="tel" {...register("mobile_number")} autoComplete="tel" placeholder="+94 77 123 4567" />
              </Field>
              <Field label="Country" error={errors.country?.message}>
                <Input {...register("country")} autoComplete="country-name" placeholder="e.g. Sri Lanka" />
              </Field>
              <Field label="Date of birth" error={errors.date_of_birth?.message}>
                <Input type="date" {...register("date_of_birth")} autoComplete="bday" />
              </Field>
              <Field label="Gender" error={errors.gender?.message}>
                <Select {...register("gender")} defaultValue="">
                  <option value="" disabled>Select gender</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </Select>
              </Field>
              <Field label="City" error={errors.city?.message}>
                <Input {...register("city")} autoComplete="address-level2" />
              </Field>
              <Field label="Address" error={errors.address?.message}>
                <Input {...register("address")} autoComplete="street-address" />
              </Field>
              <Field label="Postal code" error={errors.postal_code?.message}>
                <Input {...register("postal_code")} autoComplete="postal-code" />
              </Field>
              <Field label="Profile picture (optional)" error={pictureError ?? undefined}>
                <div className="flex items-center gap-3">
                  {picturePreview && (
                    <img
                      src={picturePreview}
                      alt="Profile preview"
                      className="h-10 w-10 rounded-full object-cover ring-1 ring-border"
                    />
                  )}
                  <Input
                    type="file"
                    accept="image/*"
                    onChange={onPictureChange}
                    className="cursor-pointer"
                  />
                </div>
              </Field>
              <Field label="Password" error={errors.password?.message}>
                <Input type="password" {...register("password")} autoComplete="new-password" />
              </Field>
              <Field label="Confirm password" error={errors.confirm_password?.message}>
                <Input type="password" {...register("confirm_password")} autoComplete="new-password" />
              </Field>

              {signupMutation.isError && (
                <div className="col-span-full rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                  {(signupMutation.error as Error).message}
                </div>
              )}
            </CardContent>

            <div className="flex flex-wrap items-center justify-between gap-2 border-t p-4">
              <div className="text-sm text-muted-foreground">
                Already have an account?{" "}
                <Link to="/login" className="font-medium text-primary underline-offset-2 hover:underline">
                  Sign in
                </Link>
              </div>
              <Button type="submit" disabled={isSubmitting || signupMutation.isPending}>
                {signupMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Create account
              </Button>
            </div>
          </form>
        </Card>
      </div>

      {showSuccess && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
          <Card className="w-full max-w-sm text-center">
            <CardContent className="flex flex-col items-center gap-3 pt-6">
              <CheckCircle2 className="h-12 w-12 text-emerald-600" />
              <div className="text-lg font-semibold">Account created successfully</div>
              <p className="text-sm text-muted-foreground">
                You can now sign in with your email and password.
              </p>
              <Button className="mt-2 w-full" onClick={() => navigate("/login", { replace: true })}>
                Go to sign in
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
      {error && <div className="text-xs text-destructive">{error}</div>}
    </div>
  );
}
