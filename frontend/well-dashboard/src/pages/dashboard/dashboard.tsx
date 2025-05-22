import Head from "next/head";

export default function Dashboard() {
  return (
    <>
      <Head>
        <title>WELL Sensor Dashboard</title>
      </Head>

      <main className="min-h-screen bg-gray-50 p-6 text-black">
        {/* Title */}
        <h1 className="text-3xl font-bold mb-6">WELL Sensor Dashboard</h1>

        {/* Top-level grid: 4 columns */}
        <div className="grid grid-cols-4 gap-4 h-[85vh]">
          {/* Filters – full height */}
          <div className="col-span-1 bg-white p-4 rounded shadow flex flex-col justify-between">
            <div>
              <h2 className="text-xl font-semibold mb-4">Filters</h2>
              <div className="space-y-2">
                <div className="bg-gray-100 h-10 rounded" /> {/* Metric */}
                <div className="bg-gray-100 h-10 rounded" /> {/* Station */}
                <div className="bg-gray-100 h-10 rounded" /> {/* Date */}
              </div>
            </div>
            <div className="mt-6 space-y-2">
              <button className="w-full bg-blue-500 text-white py-2 rounded hover:bg-blue-600">Apply</button>
              <button className="w-full bg-green-500 text-white py-2 rounded hover:bg-green-600">Download</button>
            </div>
          </div>

          {/* Right 3/4: sensor + map + graphs */}
          <div className="col-span-3 flex flex-col gap-4 h-full">
            {/* Top Row: Sensor + Map */}
            <div className="grid grid-cols-3 gap-4 flex-grow-[2] h-1/2">
              <div className="col-span-1 bg-white p-4 rounded shadow">
                <h2 className="text-xl font-semibold mb-2">Sensor Data</h2>
                <div className="space-y-2">
                  <div className="bg-gray-100 h-12 rounded p-2">Temperature</div>
                  <div className="bg-gray-100 h-12 rounded p-2">Dissolved Oxygen</div>
                  <div className="bg-gray-100 h-12 rounded p-2">Turbidity</div>
                </div>
              </div>
              <div className="col-span-2 bg-white p-4 rounded shadow">
                <h2 className="text-xl font-semibold mb-2">Map</h2>
                <div className="bg-gray-200 w-full h-full rounded">Google Map Placeholder</div>
              </div>
            </div>

            {/* Bottom Row: Graphs */}
            <div className="bg-white p-4 rounded shadow flex-grow">
              <h2 className="text-xl font-semibold mb-2">Graphs</h2>
              <div className="bg-gray-100 w-full h-full rounded h-64">Graph Placeholder</div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
