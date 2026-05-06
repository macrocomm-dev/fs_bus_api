{

"user_id": "string",
"start_time": "datetime",
"end_time": "datetime",
"start_lat": "number",
"start_lon": "number",
"end_lat": "number",
"end_lon": "number",
"device_id": "string",
"selfies": [
    {
        "timestamp": "datetime",
        "lat": "number",
        "lon": "number",
        "photo": "file"
    }
],
"busses": [
    {
        "bus_id": "string",
        "bus_number": "string",
        "inspections": [
            {
                "internal_inspection_id": "string",
                "inspection_type": ["external", "internal", "count", "driver", "technical"],Enum
                "inspection_time": "datetime",
                "inspection_lat": "number",
                "inspection_lon": "number",
                "count": "number",default 0, only for inspection_type=count
                "pass": "boolean",
                "photos": [{
                    "timestamp": "datetime",
        "lat": "number",
        "lon": "number",
        "photo": "file"
                }],
                
                "notes": "string"
            }
        ]
    }
]   
    


}