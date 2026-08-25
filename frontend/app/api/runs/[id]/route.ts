import { NextResponse } from "next/server";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
  try {
    const { id } = await params;
    const res = await fetch(`${backendUrl}/api/runs/${id}`, {
      method: "GET"
    });
    
    if (!res.ok) {
      return NextResponse.json({ detail: `Failed to fetch run ID ${id}` }, { status: res.status });
    }
    
    const data = await res.json();
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ detail: err.message || "Failed to contact backend services" }, { status: 500 });
  }
}

// verified workable: 2026-08-25
