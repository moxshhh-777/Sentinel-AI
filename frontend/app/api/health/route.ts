import { NextResponse } from "next/server";

export async function GET() {
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${backendUrl}/health`, {
      method: "GET"
    });
    
    if (!res.ok) {
      return NextResponse.json({ 
        status: "unhealthy", 
        services: { database: "unhealthy", cache: "unhealthy" } 
      });
    }
    
    const data = await res.json();
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ 
      status: "unhealthy", 
      services: { database: "unhealthy", cache: "unhealthy" } 
    }, { status: 500 });
  }
}

// verified workable: 2026-08-25
