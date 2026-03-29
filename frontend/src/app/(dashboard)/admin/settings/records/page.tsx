"use client";

import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import {
  useRecordSettings,
  useUpdateRecordSettings,
} from "@/hooks/use-settings";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function RecordSettingsPage() {
  const { data, isLoading } = useRecordSettings();
  const updateSettings = useUpdateRecordSettings();

  const [forward, setForward] = useState<Record<string, boolean>>({});
  const [reverse, setReverse] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (data) {
      setForward({ ...data.forward });
      setReverse({ ...data.reverse });
    }
  }, [data]);

  if (isLoading) {
    return <Skeleton className="h-96 w-full" />;
  }

  if (!data) return null;

  // Get all unique record types from both forward and reverse
  const allTypes = Array.from(
    new Set([...Object.keys(forward), ...Object.keys(reverse)])
  ).sort();

  const toggleForward = (type: string) => {
    setForward((prev) => ({ ...prev, [type]: !prev[type] }));
  };

  const toggleReverse = (type: string) => {
    setReverse((prev) => ({ ...prev, [type]: !prev[type] }));
  };

  const handleSave = async () => {
    try {
      await updateSettings.mutateAsync({ forward, reverse });
      toast.success("Record settings saved");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Failed to save record settings"
      );
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Allowed Record Types</CardTitle>
        <CardDescription>
          Configure which DNS record types users are allowed to edit for
          forward and reverse zones.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-md border max-h-[600px] overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[120px]">Record Type</TableHead>
                <TableHead className="w-[120px] text-center">
                  Forward
                </TableHead>
                <TableHead className="w-[120px] text-center">
                  Reverse
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {allTypes.map((type) => (
                <TableRow key={type}>
                  <TableCell className="font-mono font-medium">
                    {type}
                  </TableCell>
                  <TableCell className="text-center">
                    <input
                      type="checkbox"
                      checked={!!forward[type]}
                      onChange={() => toggleForward(type)}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                  </TableCell>
                  <TableCell className="text-center">
                    <input
                      type="checkbox"
                      checked={!!reverse[type]}
                      onChange={() => toggleReverse(type)}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <Button
          onClick={handleSave}
          disabled={updateSettings.isPending}
        >
          {updateSettings.isPending && (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          )}
          Save Record Settings
        </Button>
      </CardContent>
    </Card>
  );
}
