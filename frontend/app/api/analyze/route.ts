import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
  try {
    const body = await request.json();
    
    const res = await fetch(`${backendUrl}/api/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body)
    });
    
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      return NextResponse.json(errData, { status: res.status });
    }
    
    const data = await res.json();
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ detail: err.message || "Failed to contact backend services" }, { status: 500 });
  }
}
