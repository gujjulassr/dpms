from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def _serialize_value(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _serialize_row(row) -> dict:
    return {key: _serialize_value(value) for key, value in dict(row).items()}


def create_patient(db:Session,patient_data:dict)->dict:

    query=text(

        """
        INSERT INTO patients(
        full_name,email,phone,date_of_birth)
        VALUES
        (:full_name,:email,:phone,:date_of_birth)
        RETURNING *
        """
    )

    result=db.execute(query,patient_data)
    row=result.mappings().one()
    return _serialize_row(row)



def get_patient_by_email(db:Session,email:str)->Optional[Dict]:
    query=text(
        """
        SELECT * FROM
        patients 

        WHERE email=:email
        """
        )
    

    result=db.execute(query,{"email":email})
    row=result.mappings().first()
    return _serialize_row(row) if row else None


def get_patient_by_phone(db:Session,phone:str)->Optional[Dict]:

    query=text(
        """

        SELECT * FROM patients

        WHERE phone=:phone

        """
    )

    result=db.execute(query,{"phone":phone})
    row=result.mappings().first()
    return _serialize_row(row) if row else None


def get_patient_by_id(db:Session,patient_id:UUID)->Optional[Dict]:

    query=text(
        """
        SELECT * FROM patients

        WHERE patient_id=:patient_id
        """
    )

    result=db.execute(query,{"patient_id":str(patient_id)})
    row=result.mappings().first()
    return _serialize_row(row) if row else None


def list_patients(db:Session)->List[Dict]:

    query=text(
        """
        SELECT * FROM patients
        
        ORDER BY created_at DESC
        """
    )

    result=db.execute(query)
    rows=result.mappings().all()
    return [_serialize_row(row) for row in rows]


def get_patients_by_name(db:Session,name:str)->List[Dict]:

    query=text(
        """
        SELECT * FROM patients

        WHERE full_name ILIKE :name

        ORDER BY created_at DESC
        """
    )

    result=db.execute(query,{"name":f"%{name}%"})
    rows=result.mappings().all()
    return [_serialize_row(row) for row in rows]



def delete_patient(db: Session, patient_id: UUID) -> bool:
    """Delete a patient and their linked user account (if any). Returns True if deleted."""
    # Delete linked user account first (FK constraint)
    db.execute(
        text("DELETE FROM users WHERE patient_id = :pid"),
        {"pid": str(patient_id)},
    )
    result = db.execute(
        text("DELETE FROM patients WHERE patient_id = :pid RETURNING patient_id"),
        {"pid": str(patient_id)},
    )
    return result.rowcount > 0


def update_patient(db:Session,patient_id:UUID,patient_data:Dict)->Optional[Dict]:

    query=text(
        """
        UPDATE patients

        SET 
            full_name=:full_name,
            email=:email,
            phone=:phone,
            date_of_birth=:date_of_birth,
            updated_at=NOW()

        WHERE patient_id=:patient_id

        RETURNING *
        """
    )

    payload={
        "patient_id":str(patient_id),
        **patient_data,
    }

    result=db.execute(query,payload)
    row=result.mappings().first()
    return _serialize_row(row) if row else None
