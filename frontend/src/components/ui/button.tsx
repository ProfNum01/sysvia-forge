import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";
const buttonVariants = cva("button", {
  variants: {
    variant: {
      default: "button-primary",
      primary: "button-primary",
      outline: "button-outline",
      ghost: "button-ghost",
      destructive: "button-danger",
      success: "button-success",
      warning: "button-warning",
      agent: "button-agent",
      inspect: "button-inspect",
      subtle: "button-subtle",
    },
    size: {
      default: "",
      sm: "button-sm",
      lg: "button-lg",
      icon: "button-icon",
    },
  },
  defaultVariants: { variant: "default", size: "default" },
});
export interface ButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}
export function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}
