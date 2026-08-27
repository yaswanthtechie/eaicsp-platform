import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ApolloProvider } from "@apollo/client";

import "./index.css";
import App from "./App";
import client from "./graphql/apollo";
import ErrorBoundary from "./components/ErrorBoundary";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ApolloProvider client={client}>
        <ErrorBoundary>
          <App />
          <ToastContainer />
        </ErrorBoundary>
      </ApolloProvider>
    </BrowserRouter>
  </React.StrictMode>
);

import { registerSW } from "virtual:pwa-register";

registerSW({
  immediate: true,
});