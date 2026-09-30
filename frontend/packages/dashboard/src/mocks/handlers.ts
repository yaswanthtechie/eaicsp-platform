import { graphql } from "msw";
import { dashboardMock } from "./dashboardMock";

export const handlers = [
    graphql.query("GetDashboard", () => {
        return Response.json({
            data: {
                dashboard: dashboardMock,
            },
        });
    }),
];