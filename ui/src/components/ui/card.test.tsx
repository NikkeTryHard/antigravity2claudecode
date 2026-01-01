import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "./card";

describe("Card", () => {
  it("renders Card component", () => {
    render(<Card data-testid="card">Card content</Card>);
    expect(screen.getByTestId("card")).toBeInTheDocument();
    expect(screen.getByTestId("card")).toHaveClass("rounded-lg", "border");
  });

  it("renders CardHeader component", () => {
    render(<CardHeader data-testid="header">Header content</CardHeader>);
    expect(screen.getByTestId("header")).toBeInTheDocument();
    expect(screen.getByTestId("header")).toHaveClass("flex", "flex-col");
  });

  it("renders CardTitle component", () => {
    render(<CardTitle>Title</CardTitle>);
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Title")).toHaveClass("font-semibold");
  });

  it("renders CardDescription component", () => {
    render(<CardDescription>Description</CardDescription>);
    expect(screen.getByText("Description")).toBeInTheDocument();
    expect(screen.getByText("Description")).toHaveClass(
      "text-muted-foreground",
    );
  });

  it("renders CardContent component", () => {
    render(<CardContent data-testid="content">Content</CardContent>);
    expect(screen.getByTestId("content")).toBeInTheDocument();
    expect(screen.getByTestId("content")).toHaveClass("p-6");
  });

  it("renders CardFooter component", () => {
    render(<CardFooter data-testid="footer">Footer</CardFooter>);
    expect(screen.getByTestId("footer")).toBeInTheDocument();
    expect(screen.getByTestId("footer")).toHaveClass("flex", "items-center");
  });

  it("renders complete Card with all subcomponents", () => {
    render(
      <Card data-testid="card">
        <CardHeader>
          <CardTitle>Test Title</CardTitle>
          <CardDescription>Test Description</CardDescription>
        </CardHeader>
        <CardContent>Test Content</CardContent>
        <CardFooter>Test Footer</CardFooter>
      </Card>,
    );

    expect(screen.getByTestId("card")).toBeInTheDocument();
    expect(screen.getByText("Test Title")).toBeInTheDocument();
    expect(screen.getByText("Test Description")).toBeInTheDocument();
    expect(screen.getByText("Test Content")).toBeInTheDocument();
    expect(screen.getByText("Test Footer")).toBeInTheDocument();
  });

  it("applies custom className to Card", () => {
    render(
      <Card className="custom-class" data-testid="card">
        Content
      </Card>,
    );
    expect(screen.getByTestId("card")).toHaveClass("custom-class");
  });
});
