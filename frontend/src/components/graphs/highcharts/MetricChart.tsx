import React, { useEffect, useRef, useState } from 'react';
import Highcharts from 'highcharts';
import HighchartsReact from 'highcharts-react-official';
import useFilteredData from "@/hooks/useFilteredData";
import { SensorData, GroupSelection } from "@/hooks/useFilteredData"; // Adjust path as needed
