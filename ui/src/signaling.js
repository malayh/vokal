import { purple } from "@material-ui/core/colors";


function sleep(interval){
    return new Promise(resolve => setTimeout(resolve,interval));
}


export class ActiveConnection{
    // onTrack(stream) is a callback
    constructor(room_id, name, onTrack){
        this.pc = new RTCPeerConnection();
        
        this.name = name;
        this.room_id = room_id;
        this.ws = new WebSocket(`ws://localhost:8500`);
        
        this.ws.onopen = async (e) =>{
            await this.sendOffer();
        }

        this.ws.onmessage = this.onWSMessage.bind(this);

        
        // This is required even if you don't use it. otherwise ICE wont be collected
        this.dc = this.pc.createDataChannel("chat",{ordered: true});
        this.dc.onopen = e => {
            this.dc.send("ping");
        }
        this.dc.onmessage = async (e) =>{
            console.log(e.data);
            await sleep(1000);
            this.dc.send("ping")
        }
        
        this.pc.ontrack = async (e) =>{
            console.log(e);
            onTrack(e.streams[0]);
        }


        this.pc.onicegatheringstatechange = e => {
            console.log(this.pc.iceGatheringState);
        }
        this.pc.onsignalingstatechange = e => {
            console.log(this.pc.signalingState);
        }
    }

    async onWSMessage(e) {
        let data = JSON.parse(e.data);
        console.log(data)
        if(data.type === 'answer'){
            await this.pc.setRemoteDescription({type:"answer", sdp: data.sdp});
            return;
        }
    }



    async sendOffer(){

        // Tracks has to be added before creating the offer
        let constraints = {
            audio : true,
            video: false
        }


        let stream = await navigator.mediaDevices.getUserMedia(constraints);
        stream.getTracks().forEach((track)=> {
            this.pc.addTrack(track, stream);
        });



        let offer = await this.pc.createOffer();
        await this.pc.setLocalDescription(offer);
        
        // Block till all ICE are gathered
        while(this.pc.iceGatheringState !== 'complete')
            await sleep(500);


        this.ws.send(JSON.stringify({
            name:this.name, 
            sdp: this.pc.localDescription.sdp,
            room_id : this.room_id,
        }));

    }
}

