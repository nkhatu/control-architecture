from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status

from .config import AppSettings, get_settings, load_yaml_file
from .service import CapabilityGatewayError, CapabilityGatewayService
from .schemas import (
    BeneficiaryValidationRequest,
    BeneficiaryValidationResponse,
    DomesticPaymentInstructionRequest,
    DomesticPaymentInstructionResponse,
    PaymentStatusEnvelope,
    ReleaseApprovedPaymentRequest,
    ReleaseApprovedPaymentResponse,
)


def create_app(
    settings: AppSettings | None = None,
    service: CapabilityGatewayService | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    active_service = service or CapabilityGatewayService(
        control_plane_config=load_yaml_file(app_settings.resolved_control_plane_config_path),
        capability_registry=load_yaml_file(app_settings.resolved_capability_registry_path),
        app_name=app_settings.app_name,
        mock_rail_name=app_settings.mock_rail_name,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = app_settings
        app.state.service = active_service
        yield

    app = FastAPI(
        title="Capability Gateway",
        description="Typed domestic payment capability wrappers backed by a deterministic mock rail.",
        version="0.1.0",
        lifespan=lifespan,
    )

    def get_service() -> CapabilityGatewayService:
        return active_service

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": app_settings.app_name,
        }

    @app.get("/metadata")
    def metadata(service: CapabilityGatewayService = Depends(get_service)) -> dict[str, object]:
        return service.metadata()

    @app.post(
        "/domestic-payments/instructions",
        response_model=DomesticPaymentInstructionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_instruction(
        payload: DomesticPaymentInstructionRequest,
        service: CapabilityGatewayService = Depends(get_service),
    ) -> DomesticPaymentInstructionResponse:
        try:
            return service.create_instruction(payload)
        except CapabilityGatewayError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "error_class": exc.error_class}) from exc

    @app.post(
        "/domestic-payments/beneficiaries/validate",
        response_model=BeneficiaryValidationResponse,
    )
    def validate_beneficiary(
        payload: BeneficiaryValidationRequest,
        service: CapabilityGatewayService = Depends(get_service),
    ) -> BeneficiaryValidationResponse:
        try:
            return service.validate_beneficiary(payload)
        except CapabilityGatewayError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "error_class": exc.error_class}) from exc

    @app.post(
        "/domestic-payments/release",
        response_model=ReleaseApprovedPaymentResponse,
    )
    def release_approved_payment(
        payload: ReleaseApprovedPaymentRequest,
        service: CapabilityGatewayService = Depends(get_service),
    ) -> ReleaseApprovedPaymentResponse:
        try:
            return service.release_approved_payment(payload)
        except CapabilityGatewayError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "error_class": exc.error_class}) from exc

    @app.get(
        "/domestic-payments/{payment_id}/status",
        response_model=PaymentStatusEnvelope,
    )
    def get_payment_status(
        payment_id: str,
        service: CapabilityGatewayService = Depends(get_service),
    ) -> PaymentStatusEnvelope:
        try:
            return service.get_payment_status(payment_id)
        except CapabilityGatewayError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "error_class": exc.error_class}) from exc

    return app


app = create_app()
