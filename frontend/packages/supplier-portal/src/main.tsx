import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ApolloProvider } from "@apollo/client";

import "./index.css";
import App from "./App";
import client from "./graphql/apollo";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ApolloProvider client={client}>
        <App />
        <ToastContainer />
      </ApolloProvider>
    </BrowserRouter>
  </React.StrictMode>
);

import { registerSW } from "virtual:pwa-register";

registerSW({
  immediate: true,
}); 