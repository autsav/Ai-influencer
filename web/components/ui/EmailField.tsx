import {
  type InputHTMLAttributes,
  forwardRef,
  useId,
} from "react";
import clsx from "clsx";

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string;
}

// One email field used in Hero + SignupBlock. Phase 1 only renders — submit
// handler lives on the parent form (currently console.log).
export const EmailField = forwardRef<HTMLInputElement, Props>(
  function EmailField({ label, className, id, ...rest }, ref) {
    const autoId = useId();
    const inputId = id ?? autoId;
    return (
      <div className="flex flex-col gap-1.5">
        {label ? (
          <label
            htmlFor={inputId}
            className="text-xs font-medium uppercase tracking-wider text-ink-muted"
          >
            {label}
          </label>
        ) : null}
        <input
          ref={ref}
          id={inputId}
          type="email"
          required
          autoComplete="email"
          inputMode="email"
          placeholder="you@business.com"
          className={clsx(
            "h-12 w-full rounded-md border border-parchment-border bg-white",
            "px-4 text-base text-ink placeholder:text-ink-muted/60",
            "focus:border-terracotta focus:outline-none focus:ring-2",
            "focus:ring-terracotta/20 transition-colors",
            className,
          )}
          {...rest}
        />
      </div>
    );
  },
);