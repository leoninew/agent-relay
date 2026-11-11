from sqlalchemy.orm import Session

from agent_relay.application.context.service import ContextService
from agent_relay.infrastructure.persistence.context_queries import SQLAlchemyContextQueries
from agent_relay.infrastructure.persistence.database import Database
from agent_relay.infrastructure.persistence.repositories.context import SQLAlchemyContextRepository
from agent_relay.infrastructure.persistence.scopes import SQLAlchemyScope


class ContextWorkflow(ContextService, SQLAlchemyContextQueries):
    def __init__(self, source: Database | Session) -> None:
        ContextService.__init__(self, SQLAlchemyScope(source, SQLAlchemyContextRepository))
        SQLAlchemyContextQueries.__init__(self, source)
