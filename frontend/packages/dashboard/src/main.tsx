import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { ApolloProvider } from "@apollo/client/react";
import { BrowserRouter } from "react-router-dom";
import './index.css';
import App from './App.tsx';
import { apolloClient } from './graphql/client.ts';
import { colors } from './tokens.ts';
import { applyTokenTheme } from "./theme";

document.body.style.background = colors.bg
applyTokenTheme();

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ApolloProvider client={apolloClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ApolloProvider>
    </StrictMode>,
  )
