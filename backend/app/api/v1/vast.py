from fastapi import APIRouter, Depends, HTTPException
from app.services.vast_client import VastAIClient
from app.models.user import User
from app.api.deps import get_current_admin_user, get_current_active_user
from app.core.config import settings

router = APIRouter()


@router.get("/test-connection")
async def test_vast_connection(
    current_admin: User = Depends(get_current_admin_user)
):
    """Test Vast.ai API connection (admin only)"""
    if not settings.VAST_API_KEY:
        return {
            "status": "error",
            "api_key_configured": False,
            "error": "Vast.ai API key not configured"
        }
    
    vast_client = VastAIClient()
    
    # Test basic connection
    connection_test = await vast_client.test_connection()
    
    if connection_test["status"] == "success":
        # If connection works, try to get offers
        try:
            offers = await vast_client.get_offers(
                secure_cloud=True,
                max_cost_per_hour=999.0
            )
            
            return {
                "status": "success",
                "api_key_configured": True,
                "connection_test": connection_test,
                "secure_cloud_offers": len(offers),
                "sample_offers": offers[:2] if offers else []
            }
        except Exception as e:
            return {
                "status": "partial_success",
                "api_key_configured": True,
                "connection_test": connection_test,
                "offers_error": str(e)
            }
    else:
        return {
            "status": "error",
            "api_key_configured": True,
            "connection_test": connection_test
        }


@router.get("/offers")
async def get_vast_offers(
    max_cost: float = 10.0,
    current_admin: User = Depends(get_current_admin_user)
):
    """Get available Vast.ai offers (admin only)"""
    if not settings.VAST_API_KEY:
        raise HTTPException(status_code=503, detail="Vast.ai API key not configured")
    
    try:
        vast_client = VastAIClient()
        offers = await vast_client.get_offers(
            secure_cloud=True,
            max_cost_per_hour=max_cost
        )
        
        return {
            "offers_count": len(offers),
            "max_cost_filter": max_cost,
            "offers": offers
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/offers-for-job")
async def get_offers_for_job(
    page: int = 1,
    per_page: int = 20,
    search: str = "",
    min_gpus: int = 1,
    max_cost: float = 50.0,
    gpu_filter: str = "",
    location_filter: str = "",
    min_disk_space_gb: float = 0,
    current_user: User = Depends(get_current_active_user)
):
    """Get available Vast.ai offers for job creation with pagination and search (all users)"""
    try:
        vast_client = VastAIClient()
        offers = await vast_client.get_offers(
            secure_cloud=True,
            max_cost_per_hour=max_cost,
            region="global"
        )
        
        # Convert offers to simplified format first
        simplified_offers = []
        for offer in offers:
            simplified_offers.append({
                "id": offer.get("id"),
                "num_gpus": offer.get("num_gpus", 1),
                "gpu_name": offer.get("gpu_name", "Unknown GPU"),
                "cpu_cores": offer.get("cpu_cores", 0),
                "cpu_ram": offer.get("cpu_ram", 0),
                "gpu_ram": offer.get("gpu_ram", 0),
                "disk_space": offer.get("disk_space", 0),
                "dph_total": offer.get("dph_total", 0),
                "reliability": offer.get("reliability", 0),
                "geolocation": offer.get("geolocation", "Unknown"),
                "datacenter": offer.get("datacenter", False),
                "verified": offer.get("verified", False),
                "compute_cap": offer.get("compute_cap", 0),
                "total_flops": offer.get("total_flops", 0)
            })
        
        # Apply filters
        filtered_offers = simplified_offers
        
        # Filter by minimum GPUs
        if min_gpus > 1:
            filtered_offers = [offer for offer in filtered_offers if offer["num_gpus"] >= min_gpus]
        
        # Filter by GPU name (search in gpu_name)
        if gpu_filter:
            gpu_filter_lower = gpu_filter.lower()
            filtered_offers = [offer for offer in filtered_offers 
                             if gpu_filter_lower in offer["gpu_name"].lower()]
        
        # Filter by location
        if location_filter:
            location_filter_upper = location_filter.upper()
            filtered_offers = [offer for offer in filtered_offers 
                             if offer["geolocation"] == location_filter_upper]
        
        # Filter by minimum disk space
        if min_disk_space_gb > 0:
            filtered_offers = [offer for offer in filtered_offers 
                             if offer["disk_space"] >= min_disk_space_gb]
        
        # General search (searches in gpu_name and geolocation)
        if search:
            search_lower = search.lower()
            filtered_offers = [offer for offer in filtered_offers 
                             if search_lower in offer["gpu_name"].lower() or 
                                search_lower in offer["geolocation"].lower()]
        
        # Sort by reliability and cost (best first)
        filtered_offers.sort(key=lambda x: (-x["reliability"], x["dph_total"]))
        
        # Pagination
        total_offers = len(filtered_offers)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_offers = filtered_offers[start_idx:end_idx]
        
        return {
            "offers": paginated_offers,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_offers,
                "total_pages": (total_offers + per_page - 1) // per_page,
                "has_next": end_idx < total_offers,
                "has_prev": page > 1
            },
            "filters": {
                "search": search,
                "min_gpus": min_gpus,
                "max_cost": max_cost,
                "gpu_filter": gpu_filter,
                "location_filter": location_filter,
                "min_disk_space_gb": min_disk_space_gb
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch offers: {str(e)}")