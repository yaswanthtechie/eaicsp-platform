import strawberry

from app.graphql.mutations import Mutation
from app.graphql.queries import Query


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
)