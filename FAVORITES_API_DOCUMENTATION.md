# Job Favorites API Documentation

This document provides information about the Job Favorites API endpoints for frontend developers. Implemented using a simple Django REST Framework ModelViewSet for create, retrieve, and delete operations.

## Base URL
```
/api/linkedin/
```

## Authentication
All favorites endpoints require JWT authentication. Include the access token in the Authorization header:
```
Authorization: Bearer <your_access_token>
```

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/favorites/` | List all favorite jobs for the authenticated user |
| POST | `/favorites/` | Add a job to favorites |
| GET | `/favorites/{id}/` | Get specific favorite job details |
| DELETE | `/favorites/{id}/` | Remove a job from favorites |

---

## 1. List User Favorites

**Endpoint:** `GET /api/linkedin/favorites/`

**Description:** Retrieve all favorite jobs for the authenticated user.

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Response:**
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "job": {
        "id": 123,
        "url": "https://linkedin.com/jobs/view/123",
        "title": "Senior Python Developer",
        "company": "Tech Corp",
        "found_keywords": "python,django,api",
        "found_keywords_as_hashtags": ["#python", "#django", "#api"],
        "keywords_as_hashtags": ["#python", "#django", "#api"],
        "image": "https://example.com/image.jpg",
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T10:30:00Z",
        "description": "Job description here..."
      },
      "created_at": "2024-01-15T11:00:00Z"
    }
  ]
}
```

**Status Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Invalid or missing token
- `404 Not Found` - User profile not found

---

## 2. Add Job to Favorites

**Endpoint:** `POST /api/linkedin/favorites/`

**Description:** Add a job to the user's favorites list.

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "job_id": 123
}
```

**Response:**
```json
{
  "id": 1,
  "job": {
    "id": 123,
    "url": "https://linkedin.com/jobs/view/123",
    "title": "Senior Python Developer",
    "company": "Tech Corp",
    "found_keywords": "python,django,api",
    "found_keywords_as_hashtags": ["#python", "#django", "#api"],
    "keywords_as_hashtags": ["#python", "#django", "#api"],
    "image": "https://example.com/image.jpg",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z",
    "description": "Job description here..."
  },
  "created_at": "2024-01-15T11:00:00Z"
}
```

**Status Codes:**
- `201 Created` - Job added to favorites successfully
- `400 Bad Request` - Invalid data or job already in favorites
- `401 Unauthorized` - Invalid or missing token
- `404 Not Found` - User profile or job not found

---

## 3. Remove Job from Favorites

**Endpoint:** `DELETE /api/linkedin/favorites/{id}/`

**Description:** Remove a job from the user's favorites list.

**Headers:**
```
Authorization: Bearer <access_token>
```

**URL Parameters:**
- `id` (integer) - The ID of the favorite job to remove

**Response:**
```json
{
  "message": "Job removed from favorites"
}
```

**Status Codes:**
- `204 No Content` - Job removed successfully
- `401 Unauthorized` - Invalid or missing token
- `404 Not Found` - User profile or favorite not found

---

## 4. Get Specific Favorite Job

**Endpoint:** `GET /api/linkedin/favorites/{id}/`

**Description:** Get details of a specific favorite job.

**Headers:**
```
Authorization: Bearer <access_token>
```

**URL Parameters:**
- `id` (integer) - The ID of the favorite job

**Response:**
```json
{
  "id": 1,
  "job": {
    "id": 123,
    "url": "https://linkedin.com/jobs/view/123",
    "title": "Senior Python Developer",
    "company": "Tech Corp",
    "found_keywords": "python,django,api",
    "found_keywords_as_hashtags": ["#python", "#django", "#api"],
    "keywords_as_hashtags": ["#python", "#django", "#api"],
    "image": "https://example.com/image.jpg",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z",
    "description": "Job description here..."
  },
  "created_at": "2024-01-15T11:00:00Z"
}
```

**Status Codes:**
- `200 OK` - Success
- `401 Unauthorized` - Invalid or missing token
- `404 Not Found` - Favorite job not found

---

## Implementation Details

### Simple ModelViewSet Architecture

The favorites API uses a single `FavoriteJobViewSet` that extends Django REST Framework's `ModelViewSet` for basic CRUD operations:

- **`GET /favorites/`** - List user's favorite jobs
- **`POST /favorites/`** - Add job to favorites
- **`GET /favorites/{id}/`** - Get specific favorite details
- **`DELETE /favorites/{id}/`** - Remove from favorites

### Key Features

- **Authentication**: JWT + Session authentication
- **Permissions**: `IsAuthenticated` for all endpoints
- **User Isolation**: Each user only sees their own favorites
- **Validation**: Prevents duplicate favorites
- **Error Handling**: Proper profile validation and error responses

---

## Frontend Implementation Examples

### JavaScript/React Example

```javascript
// Add job to favorites
const addToFavorites = async (jobId) => {
  try {
    const response = await fetch('/api/linkedin/favorites/', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ job_id: jobId })
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('Job added to favorites:', data);
    } else {
      const error = await response.json();
      console.error('Error:', error);
    }
  } catch (error) {
    console.error('Network error:', error);
  }
};

// Remove job from favorites
const removeFromFavorites = async (favoriteId) => {
  try {
    const response = await fetch(`/api/linkedin/favorites/${favoriteId}/`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${access_token}`,
      }
    });
    
    if (response.ok) {
      console.log('Job removed from favorites');
    } else {
      const error = await response.json();
      console.error('Error:', error);
    }
  } catch (error) {
    console.error('Network error:', error);
  }
};

// Get user's favorite jobs
const getUserFavorites = async () => {
  try {
    const response = await fetch('/api/linkedin/favorites/', {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      return data.results;
    }
  } catch (error) {
    console.error('Network error:', error);
  }
};
```

### React Hook Example

```javascript
import { useState, useEffect } from 'react';

const useFavorites = (accessToken) => {
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(false);

  const addToFavorites = async (jobId) => {
    setLoading(true);
    try {
      const response = await fetch('/api/linkedin/favorites/add/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ job_id: jobId })
      });
      
      if (response.ok) {
        const newFavorite = await response.json();
        setFavorites(prev => [...prev, newFavorite]);
        return true;
      }
    } catch (error) {
      console.error('Error adding to favorites:', error);
    } finally {
      setLoading(false);
    }
    return false;
  };

  const removeFromFavorites = async (jobId) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/linkedin/favorites/remove/${jobId}/`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        }
      });
      
      if (response.ok) {
        setFavorites(prev => prev.filter(fav => fav.job.id !== jobId));
        return true;
      }
    } catch (error) {
      console.error('Error removing from favorites:', error);
    } finally {
      setLoading(false);
    }
    return false;
  };

  const loadFavorites = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/linkedin/favorites/', {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setFavorites(data.results);
      }
    } catch (error) {
      console.error('Error loading favorites:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (accessToken) {
      loadFavorites();
    }
  }, [accessToken]);

  return {
    favorites,
    loading,
    addToFavorites,
    removeFromFavorites,
    loadFavorites
  };
};

export default useFavorites;
```

---

## Error Handling

All endpoints return appropriate HTTP status codes and error messages. Common error scenarios:

1. **Authentication Errors (401)**
   - Missing or invalid JWT token
   - Expired access token

2. **Not Found Errors (404)**
   - User profile not found
   - Job not found

3. **Bad Request Errors (400)**
   - Invalid request data
   - Job already in favorites (when adding)
   - Job not in favorites (when removing)

4. **Server Errors (500)**
   - Internal server errors

Always handle these error cases in your frontend application to provide a good user experience.

---

## Rate Limiting

Currently, there are no specific rate limits implemented for the favorites endpoints. However, it's recommended to implement client-side throttling for actions like adding/removing favorites to prevent spam.

---

## Notes

- All timestamps are in ISO 8601 format (UTC)
- The `is_favorite` field is only included in the `jobs-with-favorites` endpoint
- Job images are returned as full URLs when available
- Keywords are provided both as raw strings and as hashtag arrays for easy frontend display
- Pagination is available for the jobs-with-favorites endpoint
