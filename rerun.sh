while true;
do
 python visa.py || echo "Script Finished/Crashed, restarting.." >&2
 echo "Press Ctrl-C to quit." && sleep 5
done