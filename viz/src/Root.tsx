import React from "react";
import {Still} from "remotion";
import {AblationChart} from "./AblationChart";
import {Cover} from "./Cover";
import {LengthChart} from "./LengthChart";

export const Root: React.FC = () => (
  <>
    <Still id="Cover" component={Cover} width={2400} height={1400} />
    <Still id="LengthLight" component={LengthChart} width={1200} height={680} defaultProps={{mode: "light" as const}} />
    <Still id="LengthDark" component={LengthChart} width={1200} height={680} defaultProps={{mode: "dark" as const}} />
    <Still id="AblationLight" component={AblationChart} width={1200} height={680} defaultProps={{mode: "light" as const}} />
    <Still id="AblationDark" component={AblationChart} width={1200} height={680} defaultProps={{mode: "dark" as const}} />
  </>
);
