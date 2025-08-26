// MongoDB test database initialization
// This script sets up test data for migration testing

// Switch to test database
db = db.getSiblingDB('testdb');

// Create collections and insert test data

// Users collection
db.users.insertMany([
    {
        _id: ObjectId(),
        username: "admin",
        email: "admin@example.com",
        password_hash: "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG",
        profile: {
            firstName: "Admin",
            lastName: "User",
            bio: "System administrator",
            avatar: "https://example.com/avatars/admin.jpg"
        },
        preferences: {
            theme: "dark",
            notifications: true,
            language: "en"
        },
        created_at: new Date(),
        updated_at: new Date(),
        is_active: true,
        roles: ["admin", "user"]
    },
    {
        _id: ObjectId(),
        username: "john_doe",
        email: "john@example.com",
        password_hash: "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG",
        profile: {
            firstName: "John",
            lastName: "Doe",
            bio: "Software developer",
            avatar: "https://example.com/avatars/john.jpg"
        },
        preferences: {
            theme: "light",
            notifications: true,
            language: "en"
        },
        created_at: new Date(),
        updated_at: new Date(),
        is_active: true,
        roles: ["user"]
    },
    {
        _id: ObjectId(),
        username: "jane_smith",
        email: "jane@example.com",
        password_hash: "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG",
        profile: {
            firstName: "Jane",
            lastName: "Smith",
            bio: "Travel blogger",
            avatar: "https://example.com/avatars/jane.jpg"
        },
        preferences: {
            theme: "light",
            notifications: false,
            language: "en"
        },
        created_at: new Date(),
        updated_at: new Date(),
        is_active: true,
        roles: ["user", "blogger"]
    }
]);

// Posts collection
db.posts.insertMany([
    {
        _id: ObjectId(),
        title: "Welcome to Our Blog",
        content: "This is the first post on our blog. Welcome!",
        slug: "welcome-to-our-blog",
        author: {
            username: "admin",
            email: "admin@example.com"
        },
        status: "published",
        tags: ["welcome", "announcement"],
        categories: ["lifestyle"],
        metadata: {
            views: 150,
            likes: 25,
            shares: 5
        },
        seo: {
            title: "Welcome to Our Amazing Blog",
            description: "Join us on our blogging journey",
            keywords: ["blog", "welcome", "community"]
        },
        created_at: new Date(),
        updated_at: new Date(),
        published_at: new Date()
    },
    {
        _id: ObjectId(),
        title: "Getting Started with Python",
        content: "Python is a great programming language for beginners. Here's how to get started...",
        slug: "getting-started-with-python",
        author: {
            username: "john_doe",
            email: "john@example.com"
        },
        status: "published",
        tags: ["python", "programming", "tutorial"],
        categories: ["technology"],
        metadata: {
            views: 320,
            likes: 45,
            shares: 12
        },
        seo: {
            title: "Python Tutorial for Beginners",
            description: "Learn Python programming from scratch",
            keywords: ["python", "tutorial", "programming", "beginners"]
        },
        code_examples: [
            {
                language: "python",
                code: "print('Hello, World!')",
                description: "Your first Python program"
            },
            {
                language: "python",
                code: "def greet(name):\n    return f'Hello, {name}!'",
                description: "A simple function"
            }
        ],
        created_at: new Date(),
        updated_at: new Date(),
        published_at: new Date()
    },
    {
        _id: ObjectId(),
        title: "My Trip to Japan",
        content: "Japan is an amazing country with rich culture and beautiful landscapes...",
        slug: "my-trip-to-japan",
        author: {
            username: "jane_smith",
            email: "jane@example.com"
        },
        status: "published",
        tags: ["travel", "japan", "culture"],
        categories: ["travel"],
        metadata: {
            views: 280,
            likes: 38,
            shares: 15
        },
        seo: {
            title: "Amazing Trip to Japan - Travel Guide",
            description: "Discover the beauty of Japan through my travel experience",
            keywords: ["japan", "travel", "culture", "guide"]
        },
        images: [
            {
                url: "https://example.com/images/japan1.jpg",
                caption: "Mount Fuji at sunrise",
                alt: "Beautiful view of Mount Fuji"
            },
            {
                url: "https://example.com/images/japan2.jpg",
                caption: "Tokyo street scene",
                alt: "Busy street in Tokyo"
            }
        ],
        location: {
            country: "Japan",
            cities: ["Tokyo", "Kyoto", "Osaka"],
            coordinates: {
                lat: 35.6762,
                lng: 139.6503
            }
        },
        created_at: new Date(),
        updated_at: new Date(),
        published_at: new Date()
    }
]);

// Comments collection
db.comments.insertMany([
    {
        _id: ObjectId(),
        post_id: db.posts.findOne({slug: "welcome-to-our-blog"})._id,
        author: {
            name: "Reader One",
            email: "reader1@example.com",
            ip: "192.168.1.100"
        },
        content: "Great first post! Looking forward to more content.",
        status: "approved",
        replies: [],
        metadata: {
            user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            referrer: "https://google.com"
        },
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        _id: ObjectId(),
        post_id: db.posts.findOne({slug: "getting-started-with-python"})._id,
        author: {
            name: "Python Fan",
            email: "pythonfan@example.com",
            ip: "192.168.1.101"
        },
        content: "Python is indeed great for beginners. Thanks for the tips!",
        status: "approved",
        replies: [
            {
                author: {
                    name: "john_doe",
                    email: "john@example.com"
                },
                content: "Thanks! Glad you found it helpful.",
                created_at: new Date()
            }
        ],
        metadata: {
            user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            referrer: "https://twitter.com"
        },
        created_at: new Date(),
        updated_at: new Date()
    }
]);

// Categories collection
db.categories.insertMany([
    {
        _id: ObjectId(),
        name: "Technology",
        slug: "technology",
        description: "Posts about technology and programming",
        color: "#007acc",
        icon: "fas fa-laptop-code",
        parent: null,
        metadata: {
            post_count: 2,
            featured: true
        },
        created_at: new Date()
    },
    {
        _id: ObjectId(),
        name: "Travel",
        slug: "travel",
        description: "Travel experiences and tips",
        color: "#28a745",
        icon: "fas fa-plane",
        parent: null,
        metadata: {
            post_count: 1,
            featured: true
        },
        created_at: new Date()
    },
    {
        _id: ObjectId(),
        name: "Lifestyle",
        slug: "lifestyle",
        description: "General lifestyle content",
        color: "#ffc107",
        icon: "fas fa-heart",
        parent: null,
        metadata: {
            post_count: 1,
            featured: false
        },
        created_at: new Date()
    }
]);

// Analytics collection (for testing complex data structures)
db.analytics.insertMany([
    {
        _id: ObjectId(),
        date: new Date(),
        page_views: {
            total: 750,
            unique: 520,
            by_page: {
                "/": 200,
                "/getting-started-with-python": 320,
                "/my-trip-to-japan": 280,
                "/welcome-to-our-blog": 150
            }
        },
        user_engagement: {
            avg_session_duration: 180,
            bounce_rate: 0.35,
            pages_per_session: 2.3
        },
        traffic_sources: {
            organic: 0.45,
            direct: 0.30,
            social: 0.15,
            referral: 0.10
        },
        devices: {
            desktop: 0.60,
            mobile: 0.35,
            tablet: 0.05
        },
        browsers: {
            chrome: 0.65,
            firefox: 0.20,
            safari: 0.10,
            edge: 0.05
        }
    }
]);

// Create indexes for performance testing
db.users.createIndex({ "username": 1 }, { unique: true });
db.users.createIndex({ "email": 1 }, { unique: true });
db.users.createIndex({ "created_at": 1 });
db.users.createIndex({ "roles": 1 });

db.posts.createIndex({ "slug": 1 }, { unique: true });
db.posts.createIndex({ "author.username": 1 });
db.posts.createIndex({ "status": 1 });
db.posts.createIndex({ "tags": 1 });
db.posts.createIndex({ "categories": 1 });
db.posts.createIndex({ "created_at": 1 });
db.posts.createIndex({ "published_at": 1 });

db.comments.createIndex({ "post_id": 1 });
db.comments.createIndex({ "status": 1 });
db.comments.createIndex({ "created_at": 1 });

db.categories.createIndex({ "slug": 1 }, { unique: true });
db.categories.createIndex({ "parent": 1 });

db.analytics.createIndex({ "date": 1 });

// Create a text index for search testing
db.posts.createIndex({
    "title": "text",
    "content": "text",
    "tags": "text"
});

print("MongoDB test database initialized successfully!");
print("Collections created: users, posts, comments, categories, analytics");
print("Indexes created for performance testing");
print("Sample data inserted for migration testing");