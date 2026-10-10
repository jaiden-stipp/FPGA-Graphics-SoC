// Physical counters sampled on the CPU pipeline edge. Counts wrap modulo 2^32.
module soc_cpu_counters (
    input logic clk, reset, memory_freeze, retired, dependency, redirect,
    output wire [159:0] statistics
);
    logic [31:0] cycles, instructions, freezes, bubbles, redirects;
    assign statistics = {cycles,instructions,freezes,bubbles,redirects};
    always_ff @(posedge clk) begin
        if (reset) begin
            cycles <= 0; instructions <= 0; freezes <= 0; bubbles <= 0; redirects <= 0;
        end else begin
            cycles <= cycles + 1'b1;
            if (!memory_freeze && retired) instructions <= instructions + 1'b1;
            if (memory_freeze) freezes <= freezes + 1'b1;
            // Flush dominates ID_EX's stall action; do not label its bubble a dependency.
            if (!memory_freeze && dependency && !redirect) bubbles <= bubbles + 1'b1;
            if (!memory_freeze && redirect) redirects <= redirects + 1'b1;
        end
    end
endmodule
