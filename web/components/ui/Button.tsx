import { type ButtonHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

type Variant = "ink" | "terracotta" | "ghost";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "md" | "lg";
}

// Two solid variants (Hero / SignupBlock) + a subtle ghost for footer-style
// CTAs later. Kept inline-class so callers don't need a Tailwind plugin.
const base =
  "inline-flex items-center justify-center font-medium tracking-tightish " +
  "rounded-md transition-colors focus-visible:outline-none " +
  "focus-visible:ring-2 focus-visible:ring-terracotta/40 " +
  "focus-visible:ring-offset-2 focus-visible:ring-offset-parchment " +
  "disabled:cursor-not-allowed disabled:opacity-60";

const variants: Record<Variant, string> = {
  ink: "bg-ink text-white hover:bg-ink/90",
  // terracotta-deep (#a4502f) + white = 5.9:1 — passes WCAG AA.
  // Spec called for terracotta DEFAULT bg; deeper variant is the AA fix.
  terracotta: "bg-terracotta-deep text-white hover:bg-terracotta",
  ghost: "bg-transparent text-ink hover:bg-parchment-sand",
};

const sizes = {
  md: "h-11 px-5 text-sm",
  lg: "h-12 px-6 text-base",
};

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "ink", size = "lg", className, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={clsx(base, variants[variant], sizes[size], className)}
      {...rest}
    />
  );
});