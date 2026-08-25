import { NextResponse } from "next/server";

export async function GET() {
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${backendUrl}/api/runs`, {
      method: "GET"
    });
    
    if (!res.ok) {
      return NextResponse.json({ detail: "Failed to fetch runs history" }, { status: res.status });
    }
    
    const data = await res.json();
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ detail: err.message || "Failed to contact backend services" }, { status: 500 });
  }
}

// verified workable: 2026-08-25
