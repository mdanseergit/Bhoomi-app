from fastapi import APIRouter

from app.api.v1 import (
    admin,
    advisories,
    auth,
    cooperation,
    crops,
    disease,
    farms,
    health,
    intelligence,
    knowledge,
    models,
    notifications,
    satellite,
    soil,
    states,
    users,
    weather,
    providers,
    farm_data,
)

api_router = APIRouter()
api_router.include_router(providers.router)
api_router.include_router(farm_data.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(farms.router)
api_router.include_router(soil.router)
api_router.include_router(weather.router)
api_router.include_router(satellite.router)
api_router.include_router(intelligence.router)
api_router.include_router(advisories.router)
api_router.include_router(disease.router)
api_router.include_router(crops.router)
api_router.include_router(models.router)
api_router.include_router(states.router)
api_router.include_router(cooperation.router)
api_router.include_router(knowledge.router)
api_router.include_router(notifications.router)
api_router.include_router(admin.router)
api_router.include_router(health.router)
