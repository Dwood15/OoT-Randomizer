const std = @import("std");
const dbg = std.debug;
const testing = std.testing;
const os = std.os;

export fn num_args(num: i32, args: [*][*]u8) i32 {
    //learning how to use allocators
    //TODO: Remove this when you actually know what you're doing :lul:
    var arena = std.heap.ArenaAllocator.init(std.heap.direct_allocator);
    defer arena.deinit();

    const a = &arena.allocator;

    var args = std.process.args();       

    const firstArg = args.next(a) orelse {
        std.debug.warn("zig could not find any args passed to the process I think?\n");
        //return [_]u8{'a'};
        return -1;
    } catch |e| {
        std.debug.warn("err getting next: {}\n", e);
        if (@errorReturnTrace()) |trace| {
            std.debug.dumpStackTrace(trace.*);
        }
        std.process.exit(1);
    };

    
    std.debug.warn("firstArg value: {}\n", firstArg);    
    return 1;
}

export fn add(a: i32, b: i32) i32 {
    return a + b;
}

test "basic add functionality" {
    testing.expect(add(3, 7) == 10);
}
