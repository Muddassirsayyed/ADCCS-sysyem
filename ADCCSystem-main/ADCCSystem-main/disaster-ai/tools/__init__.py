# ADCC Tools Package
# Exposes all operational and collection tools for agent use.

from tools.weather_tool import get_current_weather, get_forecast, get_disaster_weather
from tools.gdacs_tool import get_active_disasters, get_disaster_by_country, get_high_alert_disasters
from tools.disaster_tool import (
    get_recent_earthquakes,
    get_earthquakes_by_magnitude,
    get_earthquakes_near,
    get_india_earthquakes
)
from tools.resource_tool import (
    get_available_resources,
    get_resources_by_type,
    get_resources_by_city,
    get_resources_near,
    get_resource_summary
)
from tools.news_tool import get_disaster_news, get_news_by_country, get_news_by_keyword
from tools.route_tool import (
    get_route,
    get_evacuation_route,
    get_resource_route,
    get_alternative_routes,
    calculate_eta
)
from tools.notification_tool import (
    send_sms_alert,
    send_whatsapp_alert,
    send_email_alert,
    send_emergency_broadcast
)
from tools.social_media_tool import (
    get_disaster_mentions,
    search_disaster_keywords,
    get_location_mentions,
    detect_trending_disasters
)
from tools.satellite_tool import (
    get_satellite_metadata,
    get_flood_imagery,
    get_wildfire_imagery,
    get_disaster_imagery,
    get_latest_satellite_observations
)
