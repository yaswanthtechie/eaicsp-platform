import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ApolloProvider } from "@apollo/client/react"
import './index.css'
import App from './App.tsx'
import { apolloClient } from './graphql/client.ts'
import { colors } from './tokens.ts'

document.body.style.background = colors.bg

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ApolloProvider client={apolloClient}>
        <App />
      </ApolloProvider>
    </StrictMode>,
  )
