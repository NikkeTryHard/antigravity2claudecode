import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Badge } from "./badge";

describe("Badge", () => {
  it("renders with default variant", () => {
    render(<Badge>Default</Badge>);
    expect(screen.getByText("Default")).toBeInTheDocument();
    expect(screen.getByText("Default")).toHaveClass("bg-primary");
  });

  it("renders with secondary variant", () => {
    render(<Badge variant="secondary">Secondary</Badge>);
    expect(screen.getByText("Secondary")).toHaveClass("bg-secondary");
  });

  it("renders with destructive variant", () => {
    render(<Badge variant="destructive">Destructive</Badge>);
    expect(screen.getByText("Destructive")).toHaveClass("bg-destructive");
  });

  it("renders with outline variant", () => {
    render(<Badge variant="outline">Outline</Badge>);
    expect(screen.getByText("Outline")).toHaveClass("text-foreground");
  });

  it("renders with success variant", () => {
    render(<Badge variant="success">Success</Badge>);
    expect(screen.getByText("Success")).toHaveClass("bg-green-500");
  });

  it("renders with warning variant", () => {
    render(<Badge variant="warning">Warning</Badge>);
    expect(screen.getByText("Warning")).toHaveClass("bg-yellow-500");
  });

  it("applies custom className", () => {
    render(<Badge className="custom-class">Custom</Badge>);
    expect(screen.getByText("Custom")).toHaveClass("custom-class");
  });

  it("renders children correctly", () => {
    render(
      <Badge>
        <span data-testid="child">Child content</span>
      </Badge>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});
