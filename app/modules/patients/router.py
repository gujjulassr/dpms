from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session


from app.database.connection.database import get_db
from app.modules.patients.schemas import (
    PatientCreate,
    PatientUpdate,
    PatientResponse
)

from app.modules.patients.service import(
    create_patient_service,
    get_patient_service,
    list_patients_service,
    update_patient_service
)

router=APIRouter(prefix="/patients",tags=["Patients"])


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    name="create_patient",
)
def create_patient_endpoint(payload:PatientCreate,db:Session=Depends(get_db)):
    try:
        return create_patient_service(db,payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
            ) 




@router.get(
   "",
    response_model=List[PatientResponse],
    status_code=status.HTTP_200_OK,
    name="list_patients"
)

def list_patients_endpoint(db:Session=Depends(get_db)):
    return list_patients_service(db)



@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    name="get_patient"
)
def get_patient_endpoint(patient_id:UUID,db:Session=Depends(get_db)):
    try:
        return get_patient_service(db,patient_id)
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    


@router.patch(
    "/{patient_id}",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    name="update_patient"
)

def update_patient_endpoint(
    patient_id:UUID,
    payload:PatientUpdate,
    db:Session=Depends(get_db)
):
    try:
        return update_patient_service(db,patient_id,payload)
    
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

