"""
Slot Selection Webhook
Handles slot selection from email links
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from services.slot_selection_service import slot_selection_service
from shared.models.call_session import CallSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/slot-selection", tags=["slot-selection"])

@router.get("/")
async def handle_slot_selection(
    request: Request,
    session_id: str = Query(..., description="Call session ID"),
    agent_email: str = Query(..., description="Agent email"),
    agent_name: str = Query(..., description="Agent name"),
    slot_time: int = Query(..., description="Slot timestamp"),
    client_name: str = Query(..., description="Client name"),
    client_email: str = Query(..., description="Client email"),
    client_phone: str = Query(..., description="Client phone")
):
    """Handle slot selection from email link"""
    try:
        logger.info(f"🎯 Slot selection request: {session_id} - {client_name} - {agent_name}")
        
        # Prepare selection data
        selection_data = {
            "session_id": session_id,
            "agent_email": agent_email,
            "agent_name": agent_name,
            "slot_time": slot_time,
            "client_name": client_name,
            "client_email": client_email,
            "client_phone": client_phone
        }
        
        # Handle the slot selection
        result = await slot_selection_service.handle_slot_selection(selection_data)
        
        if result.get("success"):
            # Show success page
            return HTMLResponse(content=_get_success_html(client_name, agent_name, result), status_code=200)
        else:
            # Show error page
            return HTMLResponse(content=_get_error_html(client_name, result.get("error")), status_code=400)
            
    except Exception as e:
        logger.error(f"❌ Error handling slot selection: {e}")
        return HTMLResponse(content=_get_error_html(client_name, str(e)), status_code=500)

@router.get("/success")
async def slot_selection_success(
    client_name: str = Query(..., description="Client name"),
    agent_name: str = Query(..., description="Agent name"),
    meeting_time: str = Query(..., description="Meeting time"),
    meet_link: str = Query(None, description="Google Meet link")
):
    """Show success page for slot selection"""
    return HTMLResponse(content=_get_success_html(client_name, agent_name, {
        "meeting_time": meeting_time,
        "meet_link": meet_link
    }))

@router.get("/error")
async def slot_selection_error(
    client_name: str = Query(..., description="Client name"),
    error: str = Query(..., description="Error message")
):
    """Show error page for slot selection"""
    return HTMLResponse(content=_get_error_html(client_name, error))

def _get_success_html(client_name: str, agent_name: str, result: Dict[str, Any]) -> str:
    """Generate success HTML page"""
    meeting_time = result.get("meeting_time", "TBD")
    meet_link = result.get("meet_link", "")
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Meeting Scheduled Successfully</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                text-align: center;
            }}
            .success-icon {{
                color: #28a745;
                font-size: 48px;
                margin-bottom: 20px;
            }}
            h1 {{
                color: #333;
                margin-bottom: 20px;
            }}
            .meeting-details {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
                text-align: left;
            }}
            .meeting-details h3 {{
                color: #495057;
                margin-top: 0;
            }}
            .meeting-details p {{
                margin: 10px 0;
                color: #6c757d;
            }}
            .meet-link {{
                display: inline-block;
                background: #007bff;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                margin-top: 15px;
            }}
            .meet-link:hover {{
                background: #0056b3;
            }}
            .contact-info {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #dee2e6;
                color: #6c757d;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h1>Meeting Scheduled Successfully!</h1>
            
            <p>Hi {client_name},</p>
            <p>Your discovery call has been confirmed with {agent_name}.</p>
            
            <div class="meeting-details">
                <h3>📅 Meeting Details:</h3>
                <p><strong>Date & Time:</strong> {meeting_time}</p>
                <p><strong>Duration:</strong> 30 minutes</p>
                <p><strong>Agent:</strong> {agent_name}</p>
                <p><strong>Format:</strong> Video call</p>
            </div>
            
            {f'<a href="{meet_link}" class="meet-link" target="_blank">🎥 Join Meeting</a>' if meet_link else ''}
            
            <div class="contact-info">
                <p><strong>Need to reschedule?</strong></p>
                <p>Email: service@altruisadvisor.com</p>
                <p>Phone: 833.227.8500</p>
            </div>
        </div>
    </body>
    </html>
    """

def _get_error_html(client_name: str, error: str) -> str:
    """Generate error HTML page"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Slot Selection Error</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                text-align: center;
            }}
            .error-icon {{
                color: #dc3545;
                font-size: 48px;
                margin-bottom: 20px;
            }}
            h1 {{
                color: #333;
                margin-bottom: 20px;
            }}
            .error-message {{
                background: #f8d7da;
                color: #721c24;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                border: 1px solid #f5c6cb;
            }}
            .contact-info {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #dee2e6;
                color: #6c757d;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="error-icon">❌</div>
            <h1>Oops! Something went wrong</h1>
            
            <p>Hi {client_name},</p>
            <p>We encountered an issue while scheduling your meeting.</p>
            
            <div class="error-message">
                <strong>Error:</strong> {error}
            </div>
            
            <p>Don't worry! Our team will help you schedule your meeting manually.</p>
            
            <div class="contact-info">
                <p><strong>Contact us to schedule:</strong></p>
                <p>Email: service@altruisadvisor.com</p>
                <p>Phone: 833.227.8500</p>
                <p>We'll get back to you within 24 hours.</p>
            </div>
        </div>
    </body>
    </html>
    """
