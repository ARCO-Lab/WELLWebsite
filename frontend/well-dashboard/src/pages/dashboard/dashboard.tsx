import Head from "next/head";
import Header from "@/components/Header";
import FilterPanel from "@/components/FilterPanel";
import WeatherChart from "@/components/Chart";

export default function Dashboard() {
  return (
    <>
      <Head>
        <title>WELL Sensor Dashboard</title>
      </Head>
      <Header />
      <main className="min-h-screen p-6 text-black bg-white">
        {/* Title */}
        <h1 className="mb-6 text-3xl font-bold">WELL Sensor Dashboard</h1>

        {/* Top-level grid: 4 columns */}
        <div className="grid h-full grid-cols-4 gap-4">
          {/* Filters – full height */}
          <div className="flex flex-col justify-between col-span-1 p-4 bg-white rounded shadow">
            <div>
              <h2 className="mb-4 text-xl font-semibold">Filters</h2>
              <div className="space-y-2">
                <FilterPanel />
              </div>
            </div>
            <div className="mt-6 space-y-2">
              <button className="w-full py-2 text-white bg-yellow-500 rounded hover:bg-blue-600">Apply</button>
              <button className="w-full py-2 text-white bg-gray-600 rounded hover:bg-green-600">Download</button>
            </div>
          </div>

          {/* Right 3/4: sensor + map + graphs */}
          <div className="flex flex-col h-full col-span-3 gap-4">
            {/* Top Row: Sensor + Map */}
            <div className="grid grid-cols-3 gap-4 flex-grow-[2] h-1/2">
              <div className="col-span-1 p-4 bg-white rounded shadow">
                <h2 className="mb-2 text-xl font-semibold">Sensor Data</h2>
                <div className="space-y-2">
                  <div className="h-12 p-2 bg-gray-100 rounded h-13">Temperature</div>
                  <div className="h-12 p-2 bg-gray-100 rounded">Dissolved Oxygen</div>
                  <div className="h-12 p-2 bg-gray-100 rounded">Turbidity</div>
                </div>
              </div>
              <div className="col-span-2 p-4 bg-white rounded shadow">
                <h2 className="mb-2 text-xl font-semibold">Map</h2>
                <div className="w-full h-full bg-gray-200 rounded">Google Map Placeholder</div>
              </div>
            </div>

            {/* Bottom Row: Graphs */}
            <div className="flex-grow p-4 bg-white rounded shadow">
              <h2 className="mb-2 text-xl font-semibold">Graphs</h2>
              <WeatherChart />
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
