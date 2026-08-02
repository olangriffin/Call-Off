from pydantic import BaseModel, ConfigDict


class AuthenticatedUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    email: str
    email_verified: bool


class OrganisationAccessContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    user: AuthenticatedUser

    membership_id: str
    role: str

    organization_id: str
    organization_name: str
    organization_slug: str
