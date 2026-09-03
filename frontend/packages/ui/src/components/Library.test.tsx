import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";

import { Button } from "./Button";
import { Card } from "./Card";
import { Badge } from "./Badge";
import { KpiCard } from "./KpiCard";
import { Spinner } from "./Spinner";
import { AlertBanner } from "./AlertBanner";
import { StatusIndicator } from "./StatusIndicator";
import { Table } from "./Table";
import { Tabs } from "./Tabs/Tabs";

import { Input } from "../forms/Input";
import { Checkbox } from "../forms/Checkbox";
import { Select } from "../forms/Select";
import { TextArea } from "../forms/Textarea";

import { Sparkline } from "./charts/Sparkline";
import { Gauge } from "./charts/Gauge";
import { TrendLine } from "./charts/TrendLine";
import { MiniBarChart } from "./charts/MiniBarChart";
import { DonutChart } from "./charts/DonutChart";

describe("UI component library", () => {
  it("renders Button and handles click", () => {
    const handleClick = vi.fn();

    render(
      <Button onClick={handleClick}>
        Click me
      </Button>
    );

    fireEvent.click(screen.getByRole("button", { name: "Click me" }));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("renders Card", () => {
    render(
      <Card>
        Card content
      </Card>
    );

    expect(screen.getByText("Card content")).toBeInTheDocument();
  });

it("renders Badge", () => {
  render(<Badge status="success">Active</Badge>);

  expect(screen.getByText("Active")).toBeInTheDocument();
});

  it("renders KpiCard", () => {
    render(
      <KpiCard
        label="Revenue"
        value="$100"
      />
    );

    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("$100")).toBeInTheDocument();
  });

  it("renders Spinner", () => {
    render(<Spinner />);

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

it("renders AlertBanner", () => {
  render(
    <AlertBanner
      title="Important"
      message="Important message"
    />
  );

  expect(screen.getByText("Important")).toBeInTheDocument();
  expect(screen.getByText("Important message")).toBeInTheDocument();
});

  it("renders StatusIndicator", () => {
    render(
      <StatusIndicator status="success" />
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders Table", () => {
    render(
      <Table
        data={[
          { name: "Ashwini", value: "100" },
        ]}
        columns={[
          { key: "name", header: "Name" },
          { key: "value", header: "Value" },
        ]}
        rowKey={(row) => row.name}
      />
    );

    expect(screen.getByText("Ashwini")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("renders Tabs and changes tab", () => {
    render(
      <Tabs
        items={[
          {
            value: "one",
            label: "One",
            content: <div>One content</div>,
          },
          {
            value: "two",
            label: "Two",
            content: <div>Two content</div>,
          },
        ]}
      />
    );

    expect(screen.getByText("One content")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("tab", { name: "Two" })
    );

    expect(screen.getByText("Two content")).toBeInTheDocument();
  });

  it("renders Input", () => {
  function TestForm() {
    const methods = useForm({
      defaultValues: {
        username: "",
      },
    });

    return (
      <FormProvider {...methods}>
        <Input
          name="username"
          label="Username"
        />
      </FormProvider>
    );
  }

  render(<TestForm />);

  expect(
    screen.getByRole("textbox", { name: "Username" })
  ).toBeInTheDocument();
});
it("renders Checkbox", () => {
  function TestForm() {
    const methods = useForm({
      defaultValues: {
        terms: false,
      },
    });

    return (
      <FormProvider {...methods}>
        <Checkbox
          name="terms"
          label="Accept terms"
        />
      </FormProvider>
    );
  }

  render(<TestForm />);

  expect(
    screen.getByRole("checkbox", { name: "Accept terms" })
  ).toBeInTheDocument();
});
  

  it("renders Select", () => {
  function TestForm() {
    const methods = useForm({
      defaultValues: {
        country: "",
      },
    });

    return (
      <FormProvider {...methods}>
        <Select
          name="country"
          label="Country"
          options={[
            { value: "in", label: "India" },
            { value: "us", label: "USA" },
          ]}
        />
      </FormProvider>
    );
  }

  render(<TestForm />);

  expect(
    screen.getByRole("combobox", { name: "Country" })
  ).toBeInTheDocument();
});

it("renders TextArea", () => {
  function TestForm() {
    const methods = useForm({
      defaultValues: {
        description: "",
      },
    });

    return (
      <FormProvider {...methods}>
        <TextArea
          name="description"
          label="Description"
        />
      </FormProvider>
    );
  }

  render(<TestForm />);

  expect(
    screen.getByRole("textbox", { name: "Description" })
  ).toBeInTheDocument();
});

  it("renders Sparkline", () => {
    render(
      <Sparkline
        data={[
          { value: 10 },
          { value: 20 },
          { value: 15 },
        ]}
      />
    );

    expect(
      screen.getByRole("img", { name: "Sparkline chart" })
    ).toBeInTheDocument();
  });

  it("renders Gauge", () => {
    render(
      <Gauge
        value={75}
        label="Progress"
      />
    );

    expect(
      screen.getByRole("img", { name: "Progress: 75" })
    ).toBeInTheDocument();
  });

  it("renders TrendLine", () => {
    render(
      <TrendLine
        data={[
          { month: "Jan", value: 10 },
          { month: "Feb", value: 20 },
        ]}
        xKey="month"
        yKey="value"
      />
    );

    expect(
      document.querySelector(".chart-container")
    ).toBeInTheDocument();
  });

it("renders MiniBarChart", () => {
  const { container } = render(
    <MiniBarChart
      data={[
        { month: "Jan", value: 10 },
        { month: "Feb", value: 20 },
      ]}
      xKey="month"
      yKey="value"
    />
  );

  expect(container.firstElementChild).toBeInTheDocument();
});

it("renders DonutChart", () => {
  const { container } = render(
    <DonutChart
      data={[
        { name: "Completed", value: 70 },
        { name: "Remaining", value: 30 },
      ]}
    />
  );

  expect(container.firstElementChild).toBeInTheDocument();
});
});
