from fastapi import Depends, Request
from strawberry.fastapi import GraphQLRouter

from app.core.dependency import require_roles
from app.graphql.schema import schema


async def graphql_context(request: Request):
    return {
        "request": request,
    }


graphql_router = GraphQLRouter(
    schema,
    context_getter=graphql_context,
    dependencies=[
        Depends(require_roles("compliance_officer"))
    ],
)